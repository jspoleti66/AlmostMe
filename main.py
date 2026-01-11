import os
from flask import Flask, request, render_template, jsonify, session
from azure.ai.inference import ChatCompletionsClient
from azure.ai.inference.models import SystemMessage, UserMessage, AssistantMessage
from azure.core.credentials import AzureKeyCredential
from datetime import timedelta

app = Flask(__name__)
# Clave necesaria para encriptar las sesiones de los usuarios
app.secret_key = "mi_clave_secreta_github_2026"
app.permanent_session_lifetime = timedelta(minutes=30)

# =====================================================
# CARGA DE PROMPT Y CONOCIMIENTO (Contexto Fijo)
# =====================================================

def cargar_contexto_fijo():
    ruta_prompt = "data/prompts/system.txt"
    base_path_conocimiento = "data/conocimiento"
    
    # Cargar System Prompt
    if not os.path.exists(ruta_prompt):
        raise FileNotFoundError("❌ No se encontró data/prompts/system.txt")
        
    with open(ruta_prompt, "r", encoding="utf-8") as f:
        system_txt = f.read().strip()
    
    # Cargar Conocimiento
    conocimiento = ""
    if os.path.exists(base_path_conocimiento):
        for archivo in sorted(os.listdir(base_path_conocimiento)):
            ruta = os.path.join(base_path_conocimiento, archivo)
            if os.path.isfile(ruta):
                with open(ruta, "r", encoding="utf-8") as f:
                    conocimiento += f"\n### {archivo}\n{f.read().strip()}\n"
    
    return f"{system_txt}\n\nCONOCIMIENTO BASE:\n{conocimiento}"

# Cargamos el contexto una sola vez al iniciar el servidor
CONTEXTO_ESTATICO = cargar_contexto_fijo()

# =====================================================
# CONEXIÓN CON GITHUB MODELS
# =====================================================

def consultar_github(mensajes_historial):
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        return "⚠️ Error: Falta configurar la variable de entorno GITHUB_TOKEN"

    endpoint = "https://models.inference.ai.azure.com"
    
    try:
        client = ChatCompletionsClient(
            endpoint=endpoint,
            credential=AzureKeyCredential(token),
        )

        # 1. Inyectamos el contexto fijo (System)
        mensajes_github = [SystemMessage(content=CONTEXTO_ESTATICO)]
        
        # 2. Agregamos solo los últimos 6 mensajes para no saturar los 8k tokens de GitHub
        for msg in mensajes_historial[-6:]:
            if msg["role"] == "user":
                mensajes_github.append(UserMessage(content=msg["content"]))
            else:
                mensajes_github.append(AssistantMessage(content=msg["content"]))

        response = client.complete(
            messages=mensajes_github,
            model="meta-llama-3-3-70b-instruct",
            temperature=0.25,
            max_tokens=1500 # Limite de respuesta para ahorrar cuota
        )
        
        return response.choices[0].message.content

    except Exception as e:
        return f"⚠️ Error en GitHub Models: {str(e)}"

# =====================================================
# RUTAS FLASK
# =====================================================

@app.route("/")
def index():
    # Reiniciar historial al cargar la página principal
    session['historial'] = []
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    user_input = request.json.get("message", "").strip()
    
    if not user_input:
        return jsonify({"response": "Decime algo y seguimos."})

    # Si no existe historial en la sesión del navegador, lo creamos
    if 'historial' not in session:
        session['historial'] = []

    # Guardamos el mensaje del usuario
    session['historial'].append({"role": "user", "content": user_input})
    
    # Consultamos a GitHub Models pasándole el historial de esta sesión
    respuesta = consultar_github(session['historial'])
    
    # Guardamos la respuesta del asistente
    session['historial'].append({"role": "assistant", "content": respuesta})
    
    # Marcamos la sesión como modificada para que Flask guarde los cambios en la cookie
    session.modified = True
    
    return jsonify({"response": respuesta})

# =====================================================
# EJECUCIÓN
# =====================================================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
