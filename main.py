import os
import json
from flask import Flask, request, jsonify, render_template, session
from datetime import timedelta

from azure.ai.inference import ChatCompletionsClient
from azure.ai.inference.models import SystemMessage, UserMessage, AssistantMessage
from azure.core.credentials import AzureKeyCredential

# =====================================================
# APP
# =====================================================

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "almostme_secret")
app.permanent_session_lifetime = timedelta(minutes=30)

BASE_PATH = "data/conocimiento"
SYSTEM_PATH = "data/prompts/system.txt"

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

def cargar_conocimiento(base_path=BASE_PATH):
    conocimiento = {}

    for archivo in os.listdir(base_path):
        nombre, ext = os.path.splitext(archivo)
        ruta = os.path.join(base_path, archivo)

        if ext == ".txt":
            contenido = cargar_txt(ruta)
            if contenido:
                conocimiento[nombre] = contenido

        elif ext == ".json":
            data = cargar_json(ruta)
            if data:
                conocimiento[nombre] = json.dumps(
                    data,
                    ensure_ascii=False,
                    indent=2
                )

    return conocimiento

SYSTEM_PROMPT = cargar_txt(SYSTEM_PATH)
CONOCIMIENTO = cargar_conocimiento()

# =====================================================
# CONTEXTO GLOBAL
# =====================================================

def construir_contexto_global():
    bloques = []

    for dominio, contenido in CONOCIMIENTO.items():
        bloques.append(f"""
────────────────────────────────────────
DOMINIO: {dominio}
────────────────────────────────────────
{contenido}
""".strip())

    return f"""
{SYSTEM_PROMPT}

════════════════════════════════════════
CONOCIMIENTO PERSONAL AUTORIZADO
════════════════════════════════════════

{"\n\n".join(bloques)}
""".strip()

# =====================================================
# MODELO
# =====================================================

def consultar_modelo(historial, mensaje_usuario):
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        return "No tengo acceso al modelo."

    client = ChatCompletionsClient(
        endpoint="https://models.inference.ai.azure.com",
        credential=AzureKeyCredential(token),
    )

    mensajes = [SystemMessage(content=construir_contexto_global())]

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
        max_tokens=512,
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

    print("MENSAJE:", mensaje)

    respuesta = consultar_modelo(historial, mensaje)

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
