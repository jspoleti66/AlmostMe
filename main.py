import os
from flask import Flask, request, render_template, jsonify, session
from azure.ai.inference import ChatCompletionsClient
from azure.ai.inference.models import SystemMessage, UserMessage, AssistantMessage
from azure.core.credentials import AzureKeyCredential
from datetime import timedelta

app = Flask(__name__)

# CONFIGURACIÓN DE SESIÓN (Fundamental para Render)
app.secret_key = os.getenv("SECRET_KEY", "clave_secreta_llama_2026")
app.permanent_session_lifetime = timedelta(minutes=30)

# =====================================================
# 1. CARGA DE PROMPT Y CONOCIMIENTO (Contexto Fijo)
# =====================================================

def cargar_contexto_fijo():
    ruta_prompt = "data/prompts/system.txt"
    base_path_conocimiento = "data/conocimiento"
    
    if not os.path.exists(ruta_prompt):
        return "Eres un asistente útil." # Fallback si no hay archivo

    with open(ruta_prompt, "r", encoding="utf-8") as f:
        system_txt = f.read().strip()
    
    conocimiento = ""
    if os.path.exists(base_path_conocimiento):
        for archivo in sorted(os.listdir(base_path_conocimiento)):
            ruta = os.path.join(base_path_conocimiento, archivo)
            if os.path.isfile(ruta):
                with open(ruta, "r", encoding="utf-8") as f:
                    conocimiento += f"\n### {archivo}\n{f.read().strip()}\n"
    
    return f"{system_txt}\n\nCONOCIMIENTO BASE:\n{conocimiento}"

# Se carga una sola vez al arrancar para ahorrar recursos
CONTEXTO_ESTATICO = cargar_contexto_fijo()

# =====================================================
# 2. LÓGICA DE GITHUB MODELS (Llama 3.3 70B)
# =====================================================

def consultar_github(mensajes_historial):
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        return "⚠️ Error: Configura GITHUB_TOKEN en las variables de entorno de Render."

    endpoint = "https://models.inference.ai.azure.com"
    
    try:
        client = ChatCompletionsClient(
            endpoint=endpoint,
            credential=AzureKeyCredential(token),
        )

        # Inyectamos contexto fijo + ventana deslizante de los últimos 6 mensajes
        mensajes_github = [SystemMessage(content=CONTEXTO_ESTATICO)]
        
        for msg in mensajes_historial[-6:]:
            if msg["role"] == "user":
                mensajes_github.append(UserMessage(content=msg["content"]))
            elif msg["role"] == "assistant":
                mensajes_github.append(AssistantMessage(content=msg["content"]))

        response = client.complete(
            messages=mensajes_github,
            model="Llama-3.3-70B-Instruct", # ID exacto para GitHub Marketplace
            temperature=0.25,
            max_tokens=2048
        )
        
        # Log de consumo para monitorear en Render
        print(f"Tokens usados: {response.usage.total_tokens}")
        
        return response.choices[0].message.content

    except Exception as e:
        print(f"Error detallado en la API: {e}")
        return f"⚠️ Error de conexión: {str(e)}"

# =====================================================
# 3. RUTAS DE LA APLICACIÓN
# =====================================================

@app.route("/")
def index():
    session['historial'] = []
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    user_input = request.json.get("message", "").strip()
    
    if not user_input:
        return jsonify({"response": "Escribe algo para comenzar."})

    if 'historial' not in session:
        session['historial'] = []

    # Guardar mensaje del usuario
    session['historial'].append({"role": "user", "content": user_input})
    
    # Obtener respuesta del modelo
    respuesta = consultar_github(session['historial'])
    
    # Guardar respuesta de la IA
    session['historial'].append({"role": "assistant", "content": respuesta})
    
    # Forzar guardado de sesión
    session.modified = True
    
    return jsonify({"response": respuesta})

# =====================================================
# 4. EJECUCIÓN
# =====================================================

if __name__ == "__main__":
    # Configuración para desarrollo local
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
