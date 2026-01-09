from flask import Flask, request, render_template, jsonify, session
import os
import requests

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "almostme-secret")

# =====================================================
# CARGA DE PROMPTS
# =====================================================

def leer_archivo(path):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    print(f"⚠️ Archivo no encontrado: {path}")
    return ""

def cargar_system_prompt():
    return leer_archivo("data/prompts/system.txt")

def cargar_prompts_contextuales():
    base = "data/prompts"
    orden = [
        "identidad.txt",
        "estilo.txt",
        "reglas_interaccion.txt",
        "limites.txt"
    ]
    return "\n\n".join(leer_archivo(os.path.join(base, a)) for a in orden)

def cargar_conocimiento():
    base = "data/conocimiento"
    archivos = [
        "contactos_clave.txt",
        "cv.txt",
        "conocimiento_tecnico.txt",
        "historia_personal.txt",
        "hogar_distribucion.txt",
        "hogar_mantenimiento.txt",
        "hogar_otros.txt",
        "hogar_seguridad.txt",
        "intereses.txt",
        "personalidad.txt",
        "respuestas_frecuentes.txt"
    ]

    bloques = []
    for a in archivos:
        contenido = leer_archivo(os.path.join(base, a))
        if contenido:
            bloques.append(f"### {a}\n{contenido}")

    return "\n\n".join(bloques)

# =====================================================
# CONTEXTO BASE
# =====================================================

SYSTEM_PROMPT = cargar_system_prompt()
PROMPTS_CONTEXTUALES = cargar_prompts_contextuales()
CONOCIMIENTO = cargar_conocimiento()

def crear_historial_base():
    return [
        {
            "role": "system",
            "content": SYSTEM_PROMPT
        },
        {
            "role": "system",
            "content": (
                f"{PROMPTS_CONTEXTUALES}\n\n"
                "CONOCIMIENTO BASE (verdad factual):\n"
                f"{CONOCIMIENTO}"
            )
        }
    ]

# =====================================================
# OPENROUTER
# =====================================================

def consultar_openrouter(mensajes):
    api_key = os.getenv("OPENROUTER_API_KEY")

    if not api_key:
        return "⚠️ OPENROUTER_API_KEY no configurada en Render."

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://almostme-demo",
        "X-Title": "almostme-clon"
    }

    payload = {
        "model": "meta-llama/llama-3.3-70b-instruct:free",
        "messages": mensajes,
        "temperature": 0.3
    }

    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=30
        )

        data = response.json()

        if "choices" in data:
            return data["choices"][0]["message"]["content"]

        if "error" in data:
            return f"⚠️ Error del modelo: {data['error'].get('message', 'Desconocido')}"

        return "⚠️ Respuesta inválida del modelo."

    except Exception as e:
        return f"⚠️ Error consultando OpenRouter: {e}"

# =====================================================
# RUTAS
# =====================================================

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    user_input = request.json.get("message", "").strip()

    if not user_input:
        return jsonify({"response": "Decime algo y seguimos."})

    # Inicializar historial por sesión
    if "historial" not in session:
        session["historial"] = crear_historial_base()

    historial = session["historial"]

    historial.append({
        "role": "user",
        "content": user_input
    })

    respuesta = consultar_openrouter(historial)

    historial.append({
        "role": "assistant",
        "content": respuesta
    })

    session["historial"] = historial

    return jsonify({"response": respuesta})

@app.route("/reset", methods=["POST"])
def reset():
    session.pop("historial", None)
    return jsonify({"ok": True})

# =====================================================
# RUN
# =====================================================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)