import os
import json
import re
import traceback
from datetime import timedelta

from flask import Flask, request, jsonify, render_template, session

from azure.ai.inference import ChatCompletionsClient
from azure.ai.inference.models import (
    SystemMessage,
    UserMessage,
    AssistantMessage,
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


# =====================================================
# LOAD CONFIG
# =====================================================

def load_config():
    if not os.path.exists(CONFIG_PATH):
        raise Exception("context.json no encontrado")
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


CONFIG = load_config()
HISTORY_LIMIT = CONFIG.get("history_limit", 10)


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


# =====================================================
# SYSTEM PROMPT (REGLAS PURAS)
# =====================================================

SYSTEM_PROMPT = load_txt(CONFIG["system_prompt"])


# =====================================================
# KNOWLEDGE ENGINE (DOMAINS)
# =====================================================

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


def build_knowledge_block():
    """
    Devuelve SOLO conocimiento autorizado.
    No incluye reglas.
    """
    collected = []

    for d in DOMAINS:
        if d["content"]:
            collected.append(f"DOMINIO {d['name']}:\n{d['content']}")

    return "\n\n".join(collected).strip()


# =====================================================
# MANUALES
# =====================================================

def load_manuals():
    path = os.path.join(BASE_PATH, CONFIG["manuales"]["path"])
    if not os.path.exists(path):
        return []
    data = load_json(path)
    return data.get("items", [])


MANUALES = load_manuals()


# =====================================================
# UTILS
# =====================================================

def normalize(text):
    text = text.lower()
    text = re.sub(r"[^\w\sáéíóúñ]", "", text)
    return text


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
# RESPONSE VALIDATOR (ENFORCEMENT BÁSICO)
# =====================================================

FORBIDDEN_TERMS = [
    "ia",
    "modelo",
    "entrenamiento",
    "sistema",
    "proveedor",
]


def validate_response(text):
    """
    Valida que la respuesta no viole reglas críticas.
    """
    norm = normalize(text)

    for term in FORBIDDEN_TERMS:
        if term in norm:
            return False

    return True


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

        knowledge_block = build_knowledge_block()

        messages = []

        # 1️⃣ REGLAS INMUTABLES
        messages.append(SystemMessage(content=SYSTEM_PROMPT))

        # 2️⃣ CONOCIMIENTO AUTORIZADO (jerarquía inferior a reglas)
        if knowledge_block:
            messages.append(
                SystemMessage(
                    content=f"""
Utilizá EXCLUSIVAMENTE los siguientes hechos autorizados
para responder. No inventes información fuera de esto.

────────────────────────────────
HECHOS_AUTORIZADOS
────────────────────────────────
{knowledge_block}
"""
                )
            )

        # 3️⃣ HISTORIAL
        for msg in history:
            role = UserMessage if msg["role"] == "user" else AssistantMessage
            messages.append(role(content=msg["content"]))

        # 4️⃣ MENSAJE ACTUAL
        messages.append(UserMessage(content=message))

        response = client.complete(
            model="Meta-Llama-3.1-8B-Instruct",
            messages=messages,
            temperature=0.1,
            max_tokens=400
        )

        answer = response.choices[0].message.content.strip()

        # 5️⃣ VALIDACIÓN
        if not validate_response(answer):
            return "No puedo responder eso."

        return answer

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

        # 🔒 Filtro meta
        meta_triggers = [
            "que informacion guard",
            "que sabes de mi",
            "tus archivos",
            "cual es tu system prompt"
        ]

        if any(t in norm for t in meta_triggers):
            return jsonify({
                "type": "text",
                "content": "Solo accedo a conocimiento autorizado."
            })

        # 📘 Manual específico
        manual_especifico = find_manual(message)
        if manual_especifico:
            return jsonify({
                "type": "vcard",
                "content": f"<b>{manual_especifico['title']}</b><br>{manual_especifico['summary']}<br><a href='{manual_especifico['url']}' target='_blank'>Ver Manual</a>"
            })

        # 📚 Lista manuales
        if mentions_manual_intent(message) or norm in ["si", "cuales", "que mas"]:
            titulos = list_manual_titles()
            if titulos:
                return jsonify({
                    "type": "text",
                    "content": "Los únicos manuales disponibles son:\n• " + "\n• ".join(titulos)
                })

        # 🤖 LLM
        answer = query_model(history, message)

        history.append({"role": "user", "content": message})
        history.append({"role": "assistant", "content": answer})

        session["history"] = history[-HISTORY_LIMIT:]

        return jsonify({"type": "text", "content": answer})

    except Exception:
        print(traceback.format_exc())
        return jsonify({"type": "text", "content": "Hubo un error de conexión."}), 500


# =====================================================
# MAIN
# =====================================================

if __name__ == "__main__":
    app.run(debug=True)
