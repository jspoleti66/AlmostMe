import os
from flask import Flask, request, jsonify
from flask_cors import CORS
import requests

app = Flask(__name__)
CORS(app)

# ==============================
# CONFIGURACIÓN
# ==============================

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
MODEL = "mistralai/mistral-7b-instruct"  # podés cambiarlo

# ==============================
# CARGA SYSTEM PROMPT
# ==============================

def load_system_prompt():
    with open("system.txt", "r", encoding="utf-8") as f:
        return f.read()

SYSTEM_PROMPT = load_system_prompt()

# ==============================
# SIMULACIÓN DE BASE DE DATOS
# (Luego podés reemplazar esto por DB real)
# ==============================

def get_authorized_knowledge():
    """
    Retorna hechos personales específicos.
    Puede venir de base de datos.
    """
    # Ejemplo vacío (no bloquea identidad)
    return ""

# ==============================
# CONSTRUCCIÓN DE MENSAJES
# ==============================

def build_messages(user_message):

    messages = []

    # 1️⃣ IDENTIDAD BASE (SIEMPRE)
    messages.append({
        "role": "system",
        "content": SYSTEM_PROMPT
    })

    # 2️⃣ CONOCIMIENTO AUTORIZADO (DINÁMICO Y NO RESTRICTIVO)
    knowledge_block = get_authorized_knowledge()

    if knowledge_block:
        messages.append({
            "role": "system",
            "content": f"""
A continuación se incluyen HECHOS_AUTORIZADOS
que contienen datos personales específicos.

Reglas:

• Solo utilizalos cuando la pregunta requiera
  datos personales concretos (fechas, nombres,
  experiencias documentadas, información biográfica específica).

• Si la pregunta es general, profesional o conceptual,
  respondé normalmente según tu identidad.

• Nunca inventes datos personales.

• Si no existe información específica suficiente,
  respondé con naturalidad que preferís no dar
  ese detalle, sin bloquear la conversación.

────────────────────────────────
HECHOS_AUTORIZADOS
────────────────────────────────
{knowledge_block}
"""
        })

    # 3️⃣ MENSAJE DEL USUARIO
    messages.append({
        "role": "user",
        "content": user_message
    })

    return messages

# ==============================
# LLAMADA A OPENROUTER
# ==============================

def call_model(messages):

    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": MODEL,
            "messages": messages,
            "temperature": 0.7
        }
    )

    if response.status_code != 200:
        return f"Error en modelo: {response.text}"

    data = response.json()
    return data["choices"][0]["message"]["content"]

# ==============================
# ENDPOINT PRINCIPAL
# ==============================

@app.route("/chat", methods=["POST"])
def chat():

    user_message = request.json.get("message")

    if not user_message:
        return jsonify({"error": "Mensaje vacío"}), 400

    messages = build_messages(user_message)

    reply = call_model(messages)

    return jsonify({
        "response": reply
    })

# ==============================
# START
# ==============================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
