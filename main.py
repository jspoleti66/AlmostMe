import os
import json
from flask import Flask, request, jsonify, render_template, session
from datetime import timedelta

from azure.ai.inference import ChatCompletionsClient
from azure.ai.inference.models import SystemMessage, UserMessage, AssistantMessage
from azure.core.credentials import AzureKeyCredential

# =====================================================
# PATHS BASE (FIX RENDER)
# =====================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATA_DIR = os.path.join(BASE_DIR, "data")
CONOCIMIENTO_DIR = os.path.join(DATA_DIR, "conocimiento")

SYSTEM_PATH = os.path.join(DATA_DIR, "prompts", "system.txt")
DOMAINS_PATH = os.path.join(CONOCIMIENTO_DIR, "domains.json")
MANUALES_PATH = os.path.join(CONOCIMIENTO_DIR, "manuales.json")

# =====================================================
# APP
# =====================================================

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "almostme_secret")
app.permanent_session_lifetime = timedelta(minutes=30)

# =====================================================
# CARGA DE ARCHIVOS
# =====================================================

def cargar_txt(path):
    if not os.path.exists(path):
        return ""
    with open(path, encoding="utf-8") as f:
        return f.read().strip()

def cargar_json(path):
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def cargar_dominios_contenido(base_path):
    dominios = {}

    if not os.path.exists(base_path):
        return dominios

    for archivo in os.listdir(base_path):
        nombre, ext = os.path.splitext(archivo)
        ruta = os.path.join(base_path, archivo)

        if nombre in ("domains", "manuales"):
            continue

        if ext == ".txt":
            contenido = cargar_txt(ruta)
            if contenido:
                dominios[nombre] = {
                    "type": "text",
                    "content": contenido
                }

        elif ext == ".json":
            data = cargar_json(ruta)
            dominios[nombre] = {
                "type": "json",
                "content": data
            }

    return dominios

# =====================================================
# CARGA GLOBAL
# =====================================================

SYSTEM_PROMPT = cargar_txt(SYSTEM_PATH)
DOMAINS_CONFIG = cargar_json(DOMAINS_PATH)
DOMINIOS_CONTENIDO = cargar_dominios_contenido(CONOCIMIENTO_DIR)
MANUALES_DATA = cargar_json(MANUALES_PATH)

# =====================================================
# UTILIDADES
# =====================================================

def resolver_dominio(mensaje, domains_config):
    texto = mensaje.lower()

    for dominio, cfg in domains_config.items():
        for kw in cfg.get("keywords", []):
            if kw in texto:
                return dominio

    return None

def render_manual_vcard(manuales_json, mensaje):
    texto = mensaje.lower()
    items = manuales_json.get("items", [])

    relevantes = [
        m for m in items
        if m["title"].lower() in texto
        or any(tag in texto for tag in m.get("tags", []))
    ]

    if not relevantes:
        return "No existe un manual para eso."

    m = sorted(relevantes, key=lambda x: x.get("priority", 99))[0]

    return (
        f"**{m['title']}**\n\n"
        f"{m['summary']}\n\n"
        f"[📘 Abrir manual]({m['url']})"
    )

def construir_contexto(dominio=None):
    if not dominio or dominio not in DOMINIOS_CONTENIDO:
        return SYSTEM_PROMPT.strip()

    bloque = DOMINIOS_CONTENIDO[dominio]["content"]

    return f"""
{SYSTEM_PROMPT}

────────────────────────────────────────
CONOCIMIENTO PERSONAL AUTORIZADO
DOMINIO: {dominio}
────────────────────────────────────────

La siguiente información es el ÚNICO conocimiento personal disponible.
No existe ningún otro dato fuera de este bloque.
No completes, no infieras, no relaciones.

{bloque}
""".strip()

# =====================================================
# MODELO
# =====================================================

def consultar_modelo(historial, mensaje_usuario, dominio=None):
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        return "No tengo esa información."

    client = ChatCompletionsClient(
        endpoint="https://models.inference.ai.azure.com",
        credential=AzureKeyCredential(token),
    )

    mensajes = [SystemMessage(content=construir_contexto(dominio))]

    for msg in historial[-6:]:
        if msg["role"] == "user":
            mensajes.append(UserMessage(content=msg["content"]))
        elif msg["role"] == "assistant":
            mensajes.append(AssistantMessage(content=msg["content"]))

    mensajes.append(UserMessage(content=mensaje_usuario))

    response = client.complete(
        model="Meta-Llama-3.1-8B-Instruct",
        messages=mensajes,
        temperature=0.2,
        max_tokens=384,
        top_p=0.1
    )

    return response.choices[0].message.content.strip()

# =====================================================
# RUTAS
# =====================================================

@app.route("/")
def index():
    session.permanent = True
    session.setdefault("historial", [])
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True) or {}
    mensaje = data.get("message", "").strip()

    if not mensaje:
        return jsonify({"type": "text", "text": "Decime."})

    historial = session.get("historial", [])
    dominio = resolver_dominio(mensaje, DOMAINS_CONFIG)

    print("MENSAJE:", mensaje)
    print("DOMINIO:", dominio)

    if dominio == "manuales":
        respuesta = render_manual_vcard(MANUALES_DATA, mensaje)

    elif dominio in DOMINIOS_CONTENIDO:
        respuesta = consultar_modelo(historial, mensaje, dominio)

    else:
        respuesta = consultar_modelo(historial, mensaje, dominio=None)

    historial.append({"role": "user", "content": mensaje})
    historial.append({"role": "assistant", "content": respuesta})
    session["historial"] = historial[-12:]

    return jsonify({"type": "text", "text": respuesta})

# =====================================================
# RUN
# =====================================================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
