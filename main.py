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

    domains.sort(key=lambda x: x["priority"], reverse=True)

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
# UTILS
# =====================================================

def normalize(text):

    text = text.lower()
    text = re.sub(r"[^\w\sáéíóúñ]", "", text)

    return text


# =====================================================
# CONTEXT BUILDER
# =====================================================

def build_context(message, use_fallback=False):

    blocks = []

    if not use_fallback:

        best = find_best_domain(message)

        if best:
            blocks.append(best)

    for d in DOMAINS:

        if d not in blocks:
            blocks.append(d)

    final_blocks = []

    for d in blocks:

        final_blocks.append(
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
        + "\n".join(final_blocks[:4])
    )


# =====================================================
# DOMAIN MATCHING
# =====================================================

def score_domain(text, domain_content):

    t = set(normalize(text).split())
    d = set(normalize(domain_content).split())

    if not d:
        return 0

    return len(t & d)


def find_best_domain(message):

    scores = []

    for d in DOMAINS:

        s = score_domain(message, d["content"])

        scores.append((s, d))

    scores.sort(reverse=True, key=lambda x: x[0])

    if scores and scores[0][0] > 1:
        return scores[0][1]

    return None


# =====================================================
# MANUALES
# =====================================================

def find_manual(message):

    text = normalize(message)

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


def list_manual_titles():

    return [m["title"] for m in MANUALES]


# =====================================================
# INTENT
# =====================================================

def mentions_manual_intent(text):

    triggers = [
        "manual",
        "manuales",
        "guia",
        "guias",
        "instructivo",
        "documentacion",
        "instrucciones"
    ]

    t = normalize(text)

    return any(k in t for k in triggers)


def is_ambiguous_list(text):

    t = normalize(text)

    return "lista" in t and "manual" not in t


# =====================================================
# MODEL
# =====================================================

def query_model(history, message):

    token = os.getenv("GITHUB_TOKEN")

    if not token:
        return "No tengo acceso al modelo."

    try:

        client = ChatCompletionsClient(
            endpoint="https://models.inference.ai.azure.com",
            credential=AzureKeyCredential(token),
        )


        messages = [
            SystemMessage(content=build_context(message))
        ]


        limit = CONFIG["history_limit"]

        for msg in history[-limit:]:

            if msg["role"] == "user":

                messages.append(
                    UserMessage(content=msg["content"])
                )

            elif msg["role"] == "assistant":

                messages.append(
                    AssistantMessage(content=msg["content"])
                )


        messages.append(
            UserMessage(content=message)
        )


        response = client.complete(
            model="Meta-Llama-3.1-8B-Instruct",
            messages=messages,
            temperature=0.05,
            max_tokens=400,
            top_p=0.05
        )


        answer = response.choices[0].message.content.strip()

        return answer


    except Exception as e:

        print("MODEL ERROR:", e)
        traceback.print_exc()

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

            return jsonify({
                "type": "text",
                "content": "Decime."
            })


        history = session.get("history", [])


        norm = normalize(message)


        # ===============================
        # BLOQUEO META-INFORMACIÓN
        # ===============================

        meta_triggers = [
            "que informacion guard",
            "que datos guard",
            "que sabes de mi",
            "como funcionas",
            "como operas",
            "que archivos",
            "donde guardas",
            "tu memoria",
            "tu conocimiento"
        ]

        if any(k in norm for k in meta_triggers):

            return jsonify({
                "type": "text",
                "content": "No tengo información sobre eso."
            })


        # ===============================
        # LISTA AMBIGUA
        # ===============================

        if is_ambiguous_list(message):

            return jsonify({
                "type": "text",
                "content": "¿Lista de qué exactamente?"
            })


        # ===============================
        # MANUAL ESPECÍFICO (PRIMERO)
        # ===============================

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


        # ===============================
        # LISTA DE MANUALES (DESPUÉS)
        # ===============================

        if mentions_manual_intent(message):

            titles = list_manual_titles()

            if not titles:

                return jsonify({
                    "type": "text",
                    "content": "No tengo manuales."
                })

            txt = "Tengo estos manuales:\n\n"

            for t in titles:
                txt += f"• {t}\n"

            return jsonify({
                "type": "text",
                "content": txt.strip()
            })


        # ===============================
        # MODELO
        # ===============================

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


    except Exception as e:

        print("CHAT ERROR:", e)
        traceback.print_exc()

        return jsonify({
            "type": "text",
            "content": "Ocurrió un error interno."
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
