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
# Configuración necesaria para cookies en Render (.onrender.com)
app.config.update(
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True
)

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

# Cargamos todo al iniciar para evitar lentitud en cada mensaje
SYSTEM_PROMPT = cargar_system_prompt()
CONOCIMIENTO_TEXTO = cargar_conocimiento()

# Unificamos en un solo bloque de sistema (más estable para GitHub Models)
CONTEXTO_UNIFICADO = f"{SYSTEM_PROMPT}\n\nCONOCIMIENTO BASE:\n{CONOCIMIENTO_TEXTO}"

# =====================================================
# CONSULTA A GITHUB MODELS (LLAMA 3.3 70B)
# =====================================================

def consultar_github(historial):
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        return "⚠️ Error: GITHUB_TOKEN no configurado en Render."

    endpoint = "https://models.inference.ai.azure.com"

    try:
        client = ChatCompletionsClient(
            endpoint=endpoint,
            credential=AzureKeyCredential(token),
        )

        # Iniciamos con el contexto unificado
        mensajes = [SystemMessage(content=CONTEXTO_UNIFICADO)]

        # Ventana deslizante de conversación (últimos 8 mensajes)
        for msg in historial[-8:]:
            if msg["role"] == "user":
                mensajes.append(UserMessage(content=msg["content"]))
            elif msg["role"] == "assistant":
                mensajes.append(AssistantMessage(content=msg["content"]))

        # PETICIÓN
        response = client.complete(
            model="Llama-3.3-70B-Instruct",
            messages=mensajes,
            temperature=0.25,
            max_tokens=1024,
        )

        # ACCESO CORRECTO AL SDK 2026:
        # La respuesta de Azure AI Inference se accede mediante .choices[0].message.content
        if response and response.choices:
            return response.choices[0].message.content
        
        return "⚠️ El modelo no devolvió una respuesta válida."

    except Exception as e:
        # Esto es vital para ver el error real en los Logs de Render
        print(f"❌ ERROR CRÍTICO EN GITHUB MODELS: {type(e).__name__} - {e}")
        return f"⚠️ Error en la comunicación con la IA."

# =====================================================
# RUTAS FLASK
# =====================================================

@app.route("/")
def index():
    session.permanent = True
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

        # Agregar mensaje del usuario
        session["historial"].append({"role": "user", "content": user_input})
        
        # Consultar IA
        respuesta = consultar_github(session["historial"])

        # Agregar respuesta de la IA
        session["historial"].append({"role": "assistant", "content": respuesta})

        # Indicar a Flask que la sesión cambió para guardar la cookie
        session.modified = True

        return jsonify({"response": respuesta})

    except Exception as e:
        print(f"❌ ERROR EN RUTA /chat: {e}")
        return jsonify({"response": "⚠️ Ocurrió un error interno en el servidor."}), 500

# =====================================================
# EJECUCIÓN
# =====================================================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)


