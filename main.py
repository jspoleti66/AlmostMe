import os
import json
import requests
from flask import Flask, request, jsonify, render_template, session
from datetime import timedelta

# =====================================================
# APP
# =====================================================

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "almostme_secret_2026")
app.permanent_session_lifetime = timedelta(minutes=30)

# =====================================================
# CARGA DE CONOCIMIENTO
# =====================================================

def cargar_system_prompt():
    ruta = "data/prompts/system.txt"
    return open(ruta, encoding="utf-8").read() if os.path.exists(ruta) else ""


def cargar_conocimiento_json():
    ruta = "data/conocimiento/manuales.json"
    if not os.path.exists(ruta):
        return ""
    with open(ruta, encoding="utf-8") as f:
        return json.dumps(json.load(f), ensure_ascii=False, indent=2)


SYSTEM_PROMPT = cargar_system_prompt()
MANUALES_JSON = cargar_conocimiento_json()

# =====================================================
# MODELO (GitHub Models – RESTAURADO)
# =====================================================

def consultar_modelo(system_prompt, manuales_json, historial, mensaje_usuario):
    api_key = os.getenv("GITHUB_TOKEN")
    if not api_key:
        return "No tengo acceso al modelo en este momento."

    url = "https://models.inference.ai.azure.com/chat/completions"

    messages = [
        {
            "role": "system",
            "content": system_prompt
        },
        {
            "role": "system",
            "content": (
                "Tenés acceso a conocimiento estructurado en formato JSON "
                "sobre manuales disponibles. Usalo cuando corresponda.\n\n"
                f"{manuales_json}"
            )
        }
    ]

    messages.extend(historial)
    messages.append({"role": "user", "content": mensaje_usuario})

    payload = {
        # 🔥 MODELO ORIGINAL RESTAURADO
        "model": "gpt-4o-mini",
        "messages": messages,
        "temperature": 0.2
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    try:
        r = requests.post(url, headers=headers, json=payload, timeout=30)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print("ERROR MODELO:", e)
        return "No pude responder en este momento."

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
    data = request.get_json(silent=True)
    mensaje = data.get("message", "").strip()

    if not mensaje:
        return jsonify({"type": "text", "text": "Decime algo para comenzar."})

    historial = session.get("historial", [])

    respuesta = consultar_modelo(
        SYSTEM_PROMPT,
        MANUALES_JSON,
        historial,
        mensaje
    )

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
