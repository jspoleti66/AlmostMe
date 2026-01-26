import os
import json

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
# APP
# =====================================================

app = Flask(__name__)

app.secret_key = os.getenv("SECRET_KEY", "almostme_secret")
app.permanent_session_lifetime = timedelta(minutes=30)


# =====================================================
# PATHS
# =====================================================

BASE_PATH = "data/conocimiento"
CONFIG_PATH = "data/config/context.json"


# =====================================================
# CONFIG
# =====================================================

def load_config():

    if not os.path.exists(CONFIG_PATH):
        raise Exception("context.json no encontrado")

    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


CONFIG = load_config()


# =====================================================
# FILE LOADERS
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
# KNOWLEDGE
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

    # Prioridad descendente
    domains.sort(
        key=lambda x: x["priority"],
        reverse=True
    )

    return domains


DOMAINS = load_domains()


# =====================================================
# MANUALES
# =====================================================

def load_manuals():

    path = os.path.join(
        BASE_PATH,
        CONFIG["manuales"]["path"]
    )

    if not os.path.exists(path):
        return []

    data = load_json(path)

    return data.get("items", [])


MANUALES = load_manuals()


# =====================================================
# SYSTEM PROMPT
# =====================================================

SYSTEM_PROMPT = load_txt(
    CONFIG["system_prompt"]
)


# =====================================================
# CONTEXT BUILDER
# =====================================================

def build_global_context():

    blocks = []

    for d in DOMAINS:

        blocks.append(
            f"""
══════════════════════════════════════
DOMINIO: {d['name']}
══════════════════════════════════════

{d['content']}
"""
        )

    return (
        f"{SYSTEM_PROMPT}\n\n"
        "══════════════════════════════════════\n"
        "CONOCIMIENTO PERSONAL AUTORIZADO\n"
        "══════════════════════════════════════\n\n"
        + "\n".join(blocks)
    )


# =====================================================
# MANUAL SEARCH
# =====================================================

def find_manual(message):

    text = message.lower()

    for manual in MANUALES:

        ids = manual.get("id", "").lower().split(",")

        for key in ids:

            if key.strip() in text:
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


# =====================================================
# MODEL
# =====================================================

def query_model(history, message):

    token = os.getenv("GITHUB_TOKEN")

    if not token:
        return "No tengo acceso al modelo."

    client = ChatCompletionsClient(
        endpoint="https://models.inference.ai.azure.com",
        credential=AzureKeyCredential(token),
    )

    messages = [
        SystemMessage(
            content=build_global_context()
        )
    ]

    limit = CONFIG["history_limit"]

    for msg in history[-limit:]:

        if msg["role"] == "user":

            messages.append(
                UserMessage(
                    content=msg["content"]
                )
            )

        elif msg["role"] == "assistant":

            messages.append(
                AssistantMessage(
                    content=msg["content"]
                )
            )


    messages.append(
        UserMessage(content=message)
    )


    response = client.complete(
        model="Meta-Llama-3.1-8B-Instruct",
        messages=messages,
        temperature=0.1,
        max_tokens=512,
        top_p=0.1
    )


    return response.choices[0].message.content.strip()


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

    data = request.get_json(silent=True) or {}

    message = data.get("message", "").strip()

    if not message:

        return jsonify({
            "type": "text",
            "content": "Decime."
        })


    history = session.get("history", [])


    # ================================
    # MANUAL
    # ================================

    manual = find_manual(message)

    if manual:

        card = render_vcard(manual)

        history.extend([
            {"role": "user", "content": message},
            {"role": "assistant", "content": card}
        ])

        session["history"] = history[-12:]

        return jsonify({
            "type": "card",
            "content": card
        })


    # ================================
    # CHAT
    # ================================

    answer = query_model(history, message)


    history.extend([
        {"role": "user", "content": message},
        {"role": "assistant", "content": answer}
    ])

    session["history"] = history[-12:]


    return jsonify({
        "type": "text",
        "content": answer
    })


# =====================================================
# RUN
# =====================================================

if __name__ == "__main__":

    port = int(os.environ.get("PORT", 5000))

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False
    )
