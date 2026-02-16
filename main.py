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
# CONTEXTO UNIFICADO (ARQUITECTURA NUEVA)
# =====================================================
def build_facts_block():
    """
    Une TODOS los dominios en una única fuente de verdad.
    No hay selección parcial.
    No hay inferencia en código.
    """
    collected = []

    for d in DOMAINS:
        if d["content"]:
            collected.append(f"DOMINIO {d['name']}:\n{d['content']}")

    return "\n\n".join(collected).strip()


def build_context():
    """
    Construye el system message final unificado.
    """
    facts_block = build_facts_block()

    return f"""
{SYSTEM_PROMPT}

────────────────────────────────────────
HECHOS_AUTORIZADOS
────────────────────────────────────────

{facts_block if facts_block else "No hay hechos autorizados definidos."}

Fin del contexto.
""".strip()


# =====================================================
# MANUALES
# =====================================================
def find_manual(message):
    text = normalize(message)

    for manual in MANUALES:
        ids = [i.strip().lower() for i in manual.get("id", "").split(",")]
        for key in ids:
            if not key:
                continue
            pattern = rf"\b{key}s?\b"
            if re.search(pattern, text):
                return manual
    return None


def list_manual_titles():
    return [m["title"] for m in MANUALES if "title" in m]


def mentions_manual_intent(text):
    t = normalize(text)
    return bool(re.search(r"(manual|guia|lista|instruc|docu)", t))


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

        messages = [
            SystemMessage(content=build_context())
        ]

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

        # 1. Filtro Meta-información
        meta_triggers = ["que informacion guard", "que sabes de mi", "tus archivos"]
        if any(t in norm for t in meta_triggers):
            return jsonify({
                "type": "text",
                "content": "Solo accedo a manuales y conocimiento autorizado."
            })

        # 2. Manual específico
        manual_especifico = find_manual(message)
        if manual_especifico:
            return jsonify({
                "type": "vcard",
                "content": f"<b>{manual_especifico['title']}</b><br>{manual_especifico['summary']}<br><a href='{manual_especifico['url']}' target='_blank'>Ver Manual</a>"
            })

        # 3. Lista de manuales
        if mentions_manual_intent(message) or norm in ["si", "cuales", "que mas"]:
            titulos = list_manual_titles()
            if titulos:
                return jsonify({
                    "type": "text",
                    "content": "Los únicos manuales que tengo disponibles son:\n• " + "\n• ".join(titulos)
                })

        # 4. LLM
        answer = query_model(history, message)

        history.append({"role": "user", "content": message})
        history.append({"role": "assistant", "content": answer})
        session["history"] = history[-10:]

        return jsonify({"type": "text", "content": answer})

    except Exception:
        print(traceback.format_exc())
        return jsonify({"type": "text", "content": "Hubo un error de conexión."}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

