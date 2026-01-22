import os
import json
from flask import Flask, request, jsonify, render_template, session
from datetime import timedelta

# =====================================================
# APP
# =====================================================

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "almostme_secret")
app.permanent_session_lifetime = timedelta(minutes=30)

# =====================================================
# CARGA DE CONOCIMIENTO
# =====================================================

def cargar_archivo(path):
    if not os.path.exists(path):
        return ""
    with open(path, encoding="utf-8") as f:
        return f.read()

def cargar_json(path):
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)

SYSTEM_PROMPT = cargar_archivo("data/prompts/system.txt")
MANUALES_JSON = cargar_json("data/conocimiento/manuales.json")

# =====================================================
# GITHUB MODELS – CLIENTE REAL
# =====================================================

client = GithubModels(
    token=os.getenv("GITHUB_TOKEN")
)

def consultar_modelo(historial, mensaje_usuario):
    mensajes = []

    if SYSTEM_PROMPT:
        mensajes.append({
            "role": "system",
            "content": SYSTEM_PROMPT
        })

    if MANUALES_JSON:
        mensajes.append({
            "role": "system",
            "content": (
                "Disponés del siguiente conocimiento estructurado en JSON "
                "sobre manuales. Usalo SOLO si es relevante.\n\n"
                + json.dumps(MANUALES_JSON, ensure_ascii=False)
            )
        })

    mensajes.extend(historial)
    mensajes.append({
        "role": "user",
        "content": mensaje_usuario
    })

    try:
        response = client.complete(
            model="Meta-Llama-3.1-8B-Instruct",
            messages=mensajes,
            temperature=0.2,
            max_tokens=384,
            top_p=0.1
        )
        return response.choices[0].message.content.strip()
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
        return jsonify({"type": "text", "text": "Decime algo para empezar."})

    historial = session.get("historial", [])

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

