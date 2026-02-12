from flask import Flask, request, jsonify
import re
import requests
import os

app = Flask(__name__)

# =========================
# Configuración
# =========================

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_MODEL = "openai/gpt-4o-mini"  # o el que uses

# Manuales disponibles (fuente única de verdad)
MANUALES = [
    "Manual de Piscina",
    "Manual Peugeot 2008"
]

# =========================
# Helpers de intención
# =========================

def is_manual_list_request(text: str) -> bool:
    """
    Detecta pedidos claros y explícitos de lista de manuales.
    """
    text = text.lower().strip()
    return bool(re.search(r"\bmanuales\b", text)) or text == "manual"


def is_specific_manual_request(text: str) -> str | None:
    """
    Detecta pedidos del tipo: 'manual piscina', 'manual peugeot'
    Devuelve el nombre del manual si hay match.
    """
    text = text.lower()

    if not text.startswith("manual "):
        return None

    for manual in MANUALES:
        key = manual.lower().replace("manual ", "")
        if key in text:
            return manual

    return None


# =========================
# Respuestas hard
# =========================

def list_manuales():
    lines = "\n".join(f"• {m}" for m in MANUALES)
    return f"Los únicos manuales que tengo disponibles son:\n{lines}"


def show_manual(manual_name: str):
    # Placeholder: acá después podés linkear PDF, HTML, etc.
    return f"Puedo ayudarte con el **{manual_name}**. Decime qué información necesitás."


# =========================
# Llamada al modelo
# =========================

def call_llm(user_message: str) -> str:
    payload = {
        "model": OPENROUTER_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message}
        ]
    }

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }

    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        json=payload,
        headers=headers,
        timeout=30
    )

    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]


# =========================
# System prompt
# =========================

SYSTEM_PROMPT = """
Sos AlmostMe.

Reglas estrictas:
- NO asumas intención si el mensaje es ambiguo o está mal escrito.
- NO corrijas palabras del usuario.
- Si no entendés con claridad la consulta, respondé únicamente:
  "No entiendo con claridad tu consulta. ¿Podés reformularla?"

Tenés información personal (familia, contexto) y podés responder normalmente
cuando la pregunta sea clara.

NO inventes manuales.
NO describas contenidos de manuales inexistentes.
"""

# =========================
# Endpoint principal
# =========================

@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    user_message = data.get("message", "").strip()

    if not user_message:
        return jsonify({"response": "Hola."})

    # 1️⃣ Pedido claro de lista de manuales
    if is_manual_list_request(user_message):
        return jsonify({"response": list_manuales()})

    # 2️⃣ Pedido claro de un manual específico
    manual = is_specific_manual_request(user_message)
    if manual:
        return jsonify({"response": show_manual(manual)})

    # 3️⃣ Todo lo demás → modelo
    try:
        answer = call_llm(user_message)
        return jsonify({"response": answer})
    except Exception as e:
        return jsonify({"response": "Ocurrió un error procesando tu consulta."}), 500


if __name__ == "__main__":
    app.run(debug=True)
