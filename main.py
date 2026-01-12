import os
from flask import Flask, request, render_template, jsonify, session
from azure.ai.inference import ChatCompletionsClient
from azure.ai.inference.models import SystemMessage, UserMessage, AssistantMessage
from azure.core.credentials import AzureKeyCredential
from datetime import timedelta

app = Flask(__name__)

# =====================================================
# CONFIGURACIÓN DE SESIÓN (Render / Producción)
# =====================================================

app.secret_key = os.getenv("SECRET_KEY", "almostme_secret_2026")
app.permanent_session_lifetime = timedelta(minutes=30)

# =====================================================
# CARGA DE PROMPTS Y CONOCIMIENTO
# =====================================================

def cargar_system_prompt():
    ruta = "data/prompts/system.txt"
    if os.path.exists(ruta):
        with open(ruta, "r", encoding="utf-8") as f:
            return f.read().strip()
    return "Sos AlmostMe, el clon digital conversacional de Juan."

def cargar_conocimiento():
    base_path = "data/conocimiento"
    conocimiento = ""

    if os.path.exists(base_path):
        for archivo in sorted(os.listdir(base_path)):
            ruta = os.path.join(base_path, archivo)
            if os.path.isfile(ruta):
                with open(ruta, "r", encoding="utf-8") as f:
                    conocimiento += f"\n### {archivo}\n{f.read().strip()}\n"

    return conocimiento.strip()

SYSTEM_PROMPT = cargar_system_prompt()
CONOCIMIENTO_PROMPT = (
    "CONOCIMIENTO BASE (datos factuales, no inferir ni completar):\n"
    + cargar_conocimiento()
)

# =====================================================
# CONSULTA A GITHUB MODELS (LLAMA 3.3 70B)
# =====================================================

def consultar_github(historial):
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        return "⚠️ Error: GITHUB_TOKEN no configurado."

    endpoint = "https://models.inference.ai.azure.com"

    try:
        client = ChatCompletionsClient(
            endpoint=endpoint,
            credential=AzureKeyCredential(token),
        )

        mensajes = [
            SystemMessage(content=SYSTEM_PROMPT),
            SystemMessage(content=CONOCIMIENTO_PROMPT),
        ]

        # Ventana deslizante de conversación
        for msg in historial[-8:]:
            if msg["role"] == "user":
                mensajes.append(UserMessage(content=msg["content"]))
            elif msg["role"] == "assistant":
                mensajes.append(AssistantMessage(content=msg["content"]))

        response = client.complete(
            model="Llama-3.3-70B-Instruct",
            messages=mensajes,
            temperature=0.25,
            max_tokens=2048,
        )

        if not response.choices:
            return "⚠️ El modelo no devolvió respuesta."

        message = response.choices[0].message

        # Compatibilidad con distintas estructuras de SDK
        if isinstance(message.content, list):
            return message.content[0].text
        else:
            return message.content

    except Exception as e:
        print("❌ ERROR BACKEND (GitHub Models):", e)
        return "⚠️ Error interno procesando la respuesta."

# =====================================================
# RUTAS FLASK
# =====================================================

@app.route("/")
def index():
    if "historial" not in session:
        session["historial"] = []
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    try:
        data = request.get_json(force=True)
        user_input = data.get("message", "").strip()

        if not user_input:
            return jsonify({"response": "Decime algo para comenzar."})

        if "historial" not in session:
            session["historial"] = []

        session["historial"].append({
            "role": "user",
            "content": user_input
        })

        respuesta = consultar_github(session["historial"])

        session["historial"].append({
            "role": "assistant",
            "content": respuesta
        })

        session.modified = True

        return jsonify({"response": respuesta})

    except Exception as e:
        print("❌ ERROR EN /chat:", e)
        return jsonify({"response": "⚠️ Error interno del servidor."}), 500

# =====================================================
# RUN
# =====================================================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
