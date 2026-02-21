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
# CONFIGURACIÓN DE LA APP
# =====================================================
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "almostme_secret_key_123")
app.permanent_session_lifetime = timedelta(minutes=60)

BASE_PATH = "data/conocimiento"
CONFIG_PATH = "data/config/context.json"

def load_config():
    if not os.path.exists(CONFIG_PATH):
        return {"domains": {}, "manuales": {"path": "manuales.json"}, "system_prompt": "data/config/system.txt"}
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)

CONFIG = load_config()

# =====================================================
# CARGADORES DE DATOS
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
    conf_domains = CONFIG.get("domains", {})
    for name, cfg in conf_domains.items():
        blocks = []
        for file in cfg.get("files", []):
            path = os.path.join(BASE_PATH, file)
            content = load_txt(path)
            if content: blocks.append(content)
        if blocks:
            domains.append({
                "name": name.upper(),
                "priority": cfg.get("priority", 0),
                "content": "\n\n".join(blocks)
            })
    domains.sort(key=lambda x: x["priority"], reverse=True)
    return domains

DOMAINS = load_domains()
MANUALES = load_json(os.path.join(BASE_PATH, CONFIG["manuales"]["path"])).get("items", [])
SYSTEM_PROMPT_CONTENT = load_txt(CONFIG["system_prompt"])

# =====================================================
# UTILIDADES Y CONTEXTO
# =====================================================
def normalize(text):
    text = text.lower()
    text = re.sub(r"[^\w\sáéíóúñ]", "", text)
    return text

def build_context():
    collected = []
    for d in DOMAINS:
        if d["content"]:
            collected.append(f"### DOMINIO {d['name']}:\n{d['content']}")
    
    facts_block = "\n\n".join(collected).strip()
    
    return f"{SYSTEM_PROMPT_CONTENT}\n\n---\nHECHOS_AUTORIZADOS:\n{facts_block if facts_block else 'No hay hechos adicionales.'}\n---"

def find_manual(message):
    text = normalize(message)
    for manual in MANUALES:
        keys = [k.strip().lower() for k in manual.get("id", "").split(",")]
        if any(re.search(rf"\b{k}s?\b", text) for k in keys if k):
            return manual
    return None

# =====================================================
# MOTOR DE IA (STREAMING)
# =====================================================
def query_model_stream(history, message):
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        yield "Error: Token no configurado."
        return

    try:
        client = ChatCompletionsClient(
            endpoint="https://models.inference.ai.azure.com",
            credential=AzureKeyCredential(token),
        )

        messages = [SystemMessage(content=build_context())]
        for msg in history:
            role = UserMessage if msg["role"] == "user" else AssistantMessage
            messages.append(role(content=msg["content"]))
        messages.append(UserMessage(content=message))

        response = client.complete(
            model="Meta-Llama-3.1-8B-Instruct",
            messages=messages,
            temperature=0.1, # Casi determinista para evitar inventar
            max_tokens=500,
            stream=True
        )

        for update in response:
            if update.choices and update.choices[0].delta.content:
                yield update.choices[0].delta.content

    except Exception as e:
        print(f"Error en streaming: {e}")
        yield "Hubo un problema al conectar con mi memoria."

# =====================================================
# RUTAS
# =====================================================
@app.route("/")
def index():
    session.permanent = True
    if "history" not in session:
        session["history"] = []
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True) or {}
    message = data.get("message", "").strip()
    
    if not message:
        return jsonify({"type": "text", "content": "Decime."})

    norm = normalize(message)

    # 1. Filtro de Meta-información (Regla de Identidad)
    if any(t in norm for t in ["que informacion", "tus archivos", "quien te entreno", "que ia sos"]):
        return jsonify({"type": "text", "content": "No tengo información sobre eso."})

    # 2. Manual Específico (Short-circuit)
    manual = find_manual(message)
    if manual:
        return jsonify({
            "type": "vcard",
            "content": f"<b>{manual['title']}</b><br>{manual['summary']}<br><a href='{manual['url']}' target='_blank'>Ver Manual</a>"
        })

    # 3. Respuesta con Streaming
    def generate():
        full_reply = ""
        # Usamos un separador especial para que el JS sepa que es el inicio
        for chunk in query_model_stream(session.get("history", []), message):
            full_reply += chunk
            yield chunk # Enviamos el pedazo de texto crudo
        
        # Al terminar el stream, actualizamos el historial en la sesión
        hist = session.get("history", [])
        hist.append({"role": "user", "content": message})
        hist.append({"role": "assistant", "content": full_reply})
        session["history"] = hist[-10:]
        session.modified = True

    return Response(generate(), mimetype='text/plain')

if __name__ == "__main__":
    app.run(debug=True)
