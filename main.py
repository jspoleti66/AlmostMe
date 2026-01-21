import os
import json
from flask import Flask, request, render_template, jsonify, session
from azure.ai.inference import ChatCompletionsClient
from azure.ai.inference.models import SystemMessage, UserMessage, AssistantMessage
from azure.core.credentials import AzureKeyCredential
from datetime import timedelta

# =====================================================
# APP
# =====================================================

app = Flask(__name__)

# =====================================================
# CONFIGURACIÓN DE SESIÓN
# =====================================================

app.secret_key = os.getenv("SECRET_KEY", "almostme_secret_2026")
app.permanent_session_lifetime = timedelta(minutes=30)

app.config.update(
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True
)

# =====================================================
# MANUALES INTERNOS (FUENTE ÚNICA DE VERDAD)
# Archivos físicos en: static/manuales/
# =====================================================

MANUALES_DISPONIBLES = {
    "piscina": {
        "titulo": "Manejo de la piscina",
        "archivo": "/static/manuales/piscina.pdf",
        "keywords": [
            "piscina",
            "manual piscina",
            "manejo de la piscina",
            "mantenimiento de la piscina",
            "limpiar la piscina"
        ]
    }
}

# =====================================================
# HELPERS MANUALES
# =====================================================

def es_pedido_manual(texto: str) -> bool:
    texto = texto.lower()
    triggers = ["manual", "manuales", "documentacion", "guia", "instrucciones"]
    return any(t in texto for t in triggers)

def buscar_manual(texto: str):
    texto = texto.lower()
    for manual in MANUALES_DISPONIBLES.values():
        if any(kw in texto for kw in manual["keywords"]):
            return manual
    return None

def existe_archivo_static(ruta_publica: str) -> bool:
    ruta_relativa = ruta_publica.replace("/static/", "")
    ruta_fisica = os.path.join(app.root_path, "static", ruta_relativa)
    return os.path.exists(ruta_fisica)

# =====================================================
# SYSTEM + CONOCIMIENTO
# =====================================================

def cargar_system_prompt():
    ruta = "data/prompts/system.txt"
    if os.path.exists(ruta):
        with open(ruta, "r", encoding="utf-8") as f:
            return f.read().strip()
    return "Sos AlmostMe, el clon digital conversacional de Juan."

SYSTEM_PROMPT = cargar_system_prompt()

# =====================================================
# MODELO (LLAMA)
# =====================================================

def consultar_github(historial):
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        return "Error de configuración."

    endpoint = "https://models.inference.ai.azure.com"

    client = ChatCompletionsClient(
        endpoint=endpoint,
        credential=AzureKeyCredential(token),
    )

    mensajes = [SystemMessage(content=SYSTEM_PROMPT)]

    for msg in historial[-6:]:
        if msg["role"] == "user":
            mensajes.append(UserMessage(content=msg["content"]))
        elif msg["role"] == "assistant":
            mensajes.append(AssistantMessage(content=msg["content"]))

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
    data = request.get_json(force=True)
    user_input = data.get("message", "").strip()

    if not user_input:
        return jsonify({
            "type": "text",
            "response": "Decime algo para comenzar."
        })

    texto = user_input.lower()

    # =================================================
    # 1) TODO LO RELACIONADO A MANUALES SE RESUELVE ACÁ
    # =================================================

    if any(p in texto for p in ["manual", "manuales", "guia", "documentacion", "instrucciones", "piscina", "jardineria"]):

        manual = buscar_manual(texto)

        if manual and existe_archivo_static(manual["archivo"]):
            return jsonify({
                "type": "manual",
                "title": manual["titulo"],
                "url": manual["archivo"]
            })

        # 🔒 RESPUESTA FIJA – NO MODELO
        return jsonify({
            "type": "text",
            "response": "No tengo un manual interno sobre ese tema."
        })

    # =================================================
    # 2) RESTO → MODELO
    # =================================================

    session.setdefault("historial", [])
    session["historial"].append({
        "role": "user",
        "content": user_input
    })

    respuesta = consultar_github(session["historial"])

    session["historial"].append({
        "role": "assistant",
        "content": respuesta
    })

    session["historial"] = session["historial"][-12:]
    session.modified = True

    return jsonify({
        "type": "text",
        "response": respuesta
    })

# =====================================================
# RUN
# =====================================================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

