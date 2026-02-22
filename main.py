import os
import json
import re
import traceback

from flask import Flask, request, jsonify, render_template, session, Response
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
    if not os.path.exists(path): return ""
    with open(path, encoding="utf-8") as f:
        return f.read().strip()

def load_json(path):
    if not os.path.exists(path): return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def load_domains():
    domains = []
    for name, cfg in CONFIG["domains"].items():
        blocks = []
        for file in cfg["files"]:
            path = os.path.join(BASE_PATH, file)
            content = load_txt(path)
            if content: blocks.append(content)
        if blocks:
            domains.append({
                "name": name.upper(),
                "priority": cfg["priority"],
                "content": "\n\n".join(blocks)
            })
    domains.sort(key=lambda x: x["priority"], reverse=True)
    return domains

DOMAINS = load_domains()
MANUALES = load_json(os.path.join(BASE_PATH, CONFIG["manuales"]["path"])).get("items", [])
SYSTEM_PROMPT = load_txt(CONFIG["system_prompt"])

# =====================================================
# UTILS & CONTEXT
# =====================================================
def normalize(text):
    text = text.lower()
    text = re.sub(r"[^\w\sáéíóúñ]", "", text)
    return text

def build_context():
    collected = [f"DOMINIO {d['name']}:\n{d['content']}" for d in DOMAINS if d["content"]]
    facts_block = "\n\n".join(collected).strip()
    return f"{SYSTEM_PROMPT}\n\n────────────────\nHECHOS_AUTORIZADOS\n────────────────\n{facts_block if facts_block else 'No hay hechos.'}\nFin del contexto."

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
        if not message: return jsonify({"type": "text", "content": "Decime."})

        history = session.get("history", [])
        norm = normalize(message)

        # 1. Filtro Identidad (Basado en tu system.txt)
        if any(t in norm for t in ["ia", "modelo", "entrenamiento", "sistema"]):
            return jsonify({"type": "text", "content": "No tengo información sobre eso."})

        # 2. Manuales (Respuesta rápida JSON)
        for manual in MANUALES:
            ids = [i.strip().lower() for i in manual.get("id", "").split(",")]
            if any(re.search(rf"\b{key}s?\b", norm) for key in ids if key):
                return jsonify({
                    "type": "vcard",
                    "content": f"<b>{manual['title']}</b><br>{manual['summary']}<br><a href='{manual['url']}' target='_blank'>Ver Manual</a>"
                })

        # 3. Streaming de IA
        token = os.getenv("GITHUB_TOKEN")
        client = ChatCompletionsClient(
            endpoint="https://models.inference.ai.azure.com",
            credential=AzureKeyCredential(token),
        )

        def generate():
            full_response = ""
            messages = [SystemMessage(content=build_context())]
            for m in history:
                role = UserMessage if m["role"] == "user" else AssistantMessage
                messages.append(role(content=m["content"]))
            messages.append(UserMessage(content=message))

            response = client.complete(
                model="Meta-Llama-3.1-8B-Instruct",
                messages=messages,
                temperature=0.1,
                max_tokens=400,
                stream=True
            )

            for update in response:
                if update.choices and update.choices.delta.content:
                    content = update.choices.delta.content
                    full_response += content
                    yield content

            # Actualizamos la sesión AL FINAL del generador (usando un truco de Flask)
            # Como no podemos modificar 'session' aquí, Render lo manejará mejor si enviamos solo el texto.
            # El historial se actualizará en la próxima petición o mediante una técnica de guardado previo.

        # Guardado preventivo del lado del usuario para no romper el stream
        history.append({"role": "user", "content": message})
        session["history"] = history[-10:]

        return Response(generate(), mimetype='text/plain')

    except Exception:
        print(traceback.format_exc())
        return jsonify({"content": "Error de conexión."}), 500

if __name__ == "__main__":
    app.run(debug=True)
