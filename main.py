from flask import Flask, request, render_template, jsonify, session
import os
import requests
from datetime import timedelta

app = Flask(__name__)
# Necesitás una clave secreta para usar sesiones (puede ser cualquier texto)
app.secret_key = "clave_secreta_para_clon_llama_2026"
# La sesión expira tras 30 minutos de inactividad
app.permanent_session_lifetime = timedelta(minutes=30)

# =====================================================
# CARGA DE DATOS (Se hace una sola vez al iniciar)
# =====================================================
def cargar_contexto_fijo():
    ruta_prompt = "data/prompts/system.txt"
    base_path_conocimiento = "data/conocimiento"
    
    # Cargar System Prompt
    with open(ruta_prompt, "r", encoding="utf-8") as f:
        system_txt = f.read().strip()
    
    # Cargar Conocimiento
    conocimiento = ""
    if os.path.exists(base_path_conocimiento):
        for archivo in sorted(os.listdir(base_path_conocimiento)):
            with open(os.path.join(base_path_conocimiento, archivo), "r", encoding="utf-8") as f:
                conocimiento += f"\n### {archivo}\n{f.read().strip()}\n"
    
    return f"{system_txt}\n\nCONOCIMIENTO BASE:\n{conocimiento}"

# Cargamos el contexto en una constante global
CONTEXTO_CONFIGURADO = cargar_contexto_fijo()

# =====================================================
# LÓGICA DE OPENROUTER
# =====================================================
def consultar_openrouter(mensajes_historial):
    api_key = os.getenv("OPENROUTER_API_KEY")
    
    # 1. Armamos el payload incluyendo el contexto fijo SIEMPRE al principio
    mensajes_para_api = [
        {"role": "system", "content": CONTEXTO_CONFIGURADO}
    ]
    
    # 2. Limitamos el historial a los últimos 6 mensajes (ventana deslizante)
    # Esto evita superar los límites de tokens del modelo gratuito
    mensajes_para_api.extend(mensajes_historial[-6:])

    payload = {
        "model": "meta-llama/llama-3.3-70b-instruct:free",
        "messages": mensajes_para_api,
        "temperature": 0.25
    }

    try:
        response = requests.post(
            "openrouter.ai",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
            timeout=60
        )
        data = response.json()
        return data['choices'][0]['message']['content']
    except Exception as e:
        return f"⚠️ Error: {str(e)}"

# =====================================================
# RUTAS
# =====================================================
@app.route("/")
def index():
    # Limpiamos historial al entrar de nuevo si querés empezar de cero
    session['historial'] = []
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    user_input = request.json.get("message", "").strip()
    
    if 'historial' not in session:
        session['historial'] = []

    # Añadimos mensaje del usuario al historial de SU sesión
    session['historial'].append({"role": "user", "content": user_input})
    
    # Consultamos con la ventana deslizante
    respuesta = consultar_openrouter(session['historial'])
    
    # Añadimos respuesta de la IA al historial de SU sesión
    session['historial'].append({"role": "assistant", "content": respuesta})
    
    # Guardamos los cambios en la sesión explícitamente
    session.modified = True
    
    return jsonify({"response": respuesta})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
