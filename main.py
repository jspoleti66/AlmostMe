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

def has_ambiguous_manual_word(text):
    """
    Detecta palabras tipo:
    manuel / manueles / manules / manuall / etc.
    EXCLUYE manual y manuales
    """
    tokens = normalize(text).split()
    for t in tokens:
        if t.startswith("manu") and t not in ("manual", "manuales"):
            return True
    return False

def mentions_manual_intent(text):
    t = normalize(text)
    return bool(re.search(
        r"\b(manual|manuales|guia|guias|instrucciones|documentacion|lista de manuales)\b",
        t
    ))

def find_manual(message):
    text = normalize(message)
    for manual in MANUALES:
        ids = [i.strip().lower() for i in manual.get("id", "").split(",")]
        for key in ids:
            if not key:
                continue
            if re.search(rf"\b{re.escape(key)}\b", text):
                return manual
    return None

def list_manual_titles():
    return [m["title"] for m in MANUALES if "title" in m]

def build_context(message):
    context_text = ""
    for d in DOMAINS[:3]:
        context_text += f"\nDOMINIO {d['name']}:\n{d['content']}\n"
    return f"{SYSTEM_PROMPT}\n\nCONOCIMIENTO AUTORIZADO:\n{context_text}"

# =====================================================
# MODEL
# =====================================================
def query_model(history, message):
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        return "Error: Token no configurado."
    try:
        client = ChatCompletionsClient(
            endpoint="https://models.inference.ai.azure.com",
            credential=AzureKeyCredential(token),
        )

        messages = [SystemMessage(content=build_context(message))]
        for msg in history:
            role = UserMessage if msg["role"] == "user" else AssistantMessage
            messages.append(role(content=msg["content"]))
        messages.append(UserMessage(content=message))

        response = client.complete(
            model="Meta-Llama-3.1-8B-Instruct",
            messages=messages,
            temperature=0.1,
            max_tokens=400
        )
        return response.choices[0].message.content.strip()
    except Exception:
        return "Lo siento, no puedo responder en este momento."

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
        norm = normalize(message)

        # 1. Meta-info
        if any(t in norm for t in ["que informacion guard", "que sabes de mi", "tus archivos"]):
            return jsonify({
                "type": "text",
                "content": "Solo accedo a manuales y conocimiento técnico autorizado."
            })

        # 2. AMBIGÜEDAD → NO inferir, NO LLM
        if has_ambiguous_manual_word(message) and not mentions_manual_intent(message):
            return jsonify({
                "type": "text",
                "content": "No entiendo con claridad tu consulta. ¿Podés reformularla?"
            })

        # 3. Manual específico
        manual = find_manual(message)
        if manual:
            return jsonify({
                "type": "vcard",
                "content": (
                    f"<b>{manual['title']}</b><br>"
                    f"{manual['summary']}<br>"
                    f"<a href='{manual['url']}' target='_blank'>Ver Manual</a>"
                )
            })

        # 4. Lista de manuales (solo intención clara)
        if mentions_manual_intent(message):
            titles = list_manual_titles()
            if titles:
                return jsonify({
                    "type": "text",
                    "content": "Los únicos manuales que tengo disponibles son:\n• " + "\n• ".join(titles)
                })

        # 5. LLM
        answer = query_model(history, message)
        history.append({"role": "user", "content": message})
        history.append({"role": "assistant", "content": answer})
        session["history"] = history[-10:]

        return jsonify({"type": "text", "content": answer})

    except Exception:
        print(traceback.format_exc())
        return jsonify({"type": "text", "content": "Hubo un error de conexión."}), 500

if __name__ == "__main__":
    app.run(debug=True)
