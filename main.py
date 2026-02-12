import os
import json
import re
import traceback

from flask import Flask, request, jsonify, render_template, session
from datetime import timedelta

from azure.ai.inference import ChatCompletionsClient
from azure.ai.inference.models import (
    SystemMessage,
    UserMessage,
    AssistantMessage
)
from azure.core.credentials import AzureKeyCredential

# =====================================================
# APP CONFIG
# =====================================================
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "almostme_secret")
app.permanent_session_lifetime = timedelta(minutes=30)

BASE_PATH = "data/conocimiento"
CONFIG_PATH = "data/config/context.json"

def load_config():
    if not os.path.exists(CONFIG_PATH):
        raise Exception("context.json no encontrado")
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)

CONFIG = load_config()

# =====================================================
# LOADERS
# =====================================================
def load_txt(path):
    if not os.path.exists(path):
        return ""
    with open(path, encoding="utf-8") as f:
        return f.read().strip()

def load_json(path):
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def load_domains():
    domains = []
    for name, cfg in CONFIG["domains"].items():
        blocks = []
        for file in cfg["files"]:
            path = os.path.join(BASE_PATH, file)
            content = load_txt(path)
            if content:
                blocks.append(content)
        if blocks:
            domains.append({
                "name": name.upper(),
                "priority": cfg["priority"],
                "content": "\n\n".join(blocks)
            })
    domains.sort(key=lambda x: x["priority"], reverse=True)
    return domains

DOMAINS = load_domains()

def load_manuals():
    path = os.path.join(BASE_PATH, CONFIG["manuales"]["path"])
    if not os.path.exists(path):
        return []
    data = load_json(path)
    return data.get("items", [])

MANUALES = load_manuals()
SYSTEM_PROMPT = load_txt(CONFIG["system_prompt"])

# =====================================================
# UTILS
# =====================================================
def normalize(text):
    text = text.lower()
    text = re.sub(r"[^\w\sáéíóúñ]", "", text)
    return text

# =====================================================
# MANUALES (BACKEND PURO)
# =====================================================
def mentions_manual_intent(text):
    t = normalize(text)
    return bool(re.search(
        r"\b(manual(es)?|manueles|manules|manualles)\b",
        t
    ))

def is_list_manual_request(text):
    t = normalize(text)
    triggers = [
        "que manuales",
        "cuales manuales",
        "lista de manuales",
        "manuales tienes",
        "manuales tenes"
    ]
    return any(k in t for k in triggers)

def find_manual(text):
    t = normalize(text)
    for manual in MANUALES:
        ids = [i.strip().lower() for i in manual.get("id", "").split(",")]
        for key in ids:
            if not key:
                continue
            if re.search(rf"\b{key}s?\b", t):
                return manual
    return None

def render_vcard(manual):
    return f"""
<div class="vcard">
  <strong>{manual['title']}</strong><br>
  <span>{manual['summary']}</span><br>
  <a href="{manual['url']}" target="_blank" rel="noopener">Abrir manual</a>
</div>
"""

def list_manual_titles():
    return [m["title"] for m in MANUALES]

# =====================================================
# MODEL
# =====================================================
def build_context(message):
    return f"{SYSTEM_PROMPT}"

def query_model(history, message):
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        return "No puedo responder en este momento."

    try:
        client = ChatCompletionsClient(
            endpoint="https://models.inference.ai.azure.com",
            credential=AzureKeyCredential(token),
        )

        messages = [SystemMessage(content=build_context(message))]

        for msg in history[-8:]:
            cls = UserMessage if msg["role"] == "user" else AssistantMessage
            messages.append(cls(content=msg["content"]))

        messages.append(UserMessage(content=message))

        response = client.complete(
            model="Meta-Llama-3.1-8B-Instruct",
            messages=messages,
            temperature=0.1,
            max_tokens=400
        )

        return response.choices[0].message.content.strip()

    except Exception:
        return "No puedo responder en este momento."

# =====================================================
# ROUTES
# =====================================================
@app.route("/")
def index():
    session.permanent = True
    session.setdefault("history", [])
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    try:
        data = request.get_json(silent=True) or {}
        message = data.get("message", "").strip()

        if not message:
            return jsonify({"type": "text", "content": "Decime."})

        history = session.get("history", [])

        # =================================================
        # BLOQUE MANUALES (CIERRE TOTAL AL MODELO)
        # =================================================
        if mentions_manual_intent(message):

            manual = find_manual(message)
            if manual:
                return jsonify({
                    "type": "card",
                    "content": render_vcard(manual)
                })

            if is_list_manual_request(message):
                titles = list_manual_titles()
                if not titles:
                    return jsonify({
                        "type": "text",
                        "content": "No tengo manuales registrados."
                    })

                txt = "Los únicos manuales que tengo disponibles son:\n"
                for t in titles:
                    txt += f"• {t}\n"

                return jsonify({
                    "type": "text",
                    "content": txt.strip()
                })

            return jsonify({
                "type": "text",
                "content": "No tengo información sobre ese manual."
            })

        # =================================================
        # MODELO (solo si no fue manual)
        # =================================================
        answer = query_model(history, message)

        history.append({"role": "user", "content": message})
        history.append({"role": "assistant", "content": answer})
        session["history"] = history[-10:]

        return jsonify({"type": "text", "content": answer})

    except Exception:
        print(traceback.format_exc())
        return jsonify({
            "type": "text",
            "content": "Hubo un error de conexión."
        }), 500

# =====================================================
# RUN
# =====================================================
if __name__ == "__main__":
    app.run(debug=True)
