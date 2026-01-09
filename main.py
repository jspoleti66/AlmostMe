from flask import Flask, request, render_template, jsonify
import os
import requests

app = Flask(__name__)

# =====================================================
# CARGA DE PROMPTS
# =====================================================

def cargar_system_prompt():
    ruta = "data/prompts/system.txt"
    if os.path.exists(ruta):
        with open(ruta, "r", encoding="utf-8") as f:
            return f.read().strip()
    else:
        print("⚠️ system.txt no encontrado")
        return ""

def cargar_prompts_contextuales():
    base_path = "data/prompts"
    orden = [
        "identidad.txt",
        "estilo.txt",
        "reglas_interaccion.txt",
        "limites.txt"
    ]

    contenido = ""
    for archivo in orden:
        ruta = os.path.join(base_path, archivo)
        if os.path.exists(ruta):
            with open(ruta, "r", encoding="utf-8") as f:
                contenido += f"\n{f.read()}\n"
        else:
            print(f"⚠️ Prompt no encontrado: {ruta}")

    return contenido.strip()

def cargar_conocimiento():
    base_path = "data/conocimiento"
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

    conocimiento = ""
    for archivo in archivos:
        ruta = os.path.join(base_path, archivo)
        if os.path.exists(ruta):
            with open(ruta, "r", encoding="utf-8") as f:
                conocimiento += f"\n### {archivo}\n{f.read()}\n"
        else:
            print(f"⚠️ Archivo de conocimiento no encontrado: {ruta}")

    return conocimiento.strip()

# =====================================================
# OPENROUTER
# =====================================================

def consultar_openrouter(mensajes):
    api_key = os.getenv("OPENROUTER_API_KEY")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://almostme-demo",
        "X-Title": "almostme-clon"
    }

    payload = {
        "model": "meta-llama/llama-4-maverick",
        "messages": mensajes,
        "temperature": 0.4
    }

    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers=headers,
        json=payload
    )

    try:
        data = response.json()
        if "choices" in data:
            return data["choices"][0]["message"]["content"]
        elif "error" in data:
            return f"⚠️ Error del modelo: {data['error'].get('message', 'Desconocido')}"
        else:
            return "⚠️ El modelo no devolvió respuesta válida."
    except Exception as e:
        return f"⚠️ Error procesando la respuesta: {e}"

# =====================================================
# INICIALIZACIÓN DE CONVERSACIÓN
# =====================================================

system_prompt = cargar_system_prompt()
prompts_contextuales = cargar_prompts_contextuales()
conocimiento = cargar_conocimiento()

historial = [
    {
        "role": "system",
        "content": system_prompt
    },
    {
        "role": "system",
        "content": (
            f"{prompts_contextuales}\n\n"
            "CONOCIMIENTO BASE (verdad factual):\n"
            f"{conocimiento}"
        )
    }
]

# =====================================================
# RUTAS FLASK
# =====================================================

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    user_input = request.json.get("message", "").strip()

    if not user_input:
        return jsonify({"response": "Decime algo y seguimos."})

    historial.append({
        "role": "user",
        "content": user_input
    })

    respuesta = consultar_openrouter(historial)

    historial.append({
        "role": "assistant",
        "content": respuesta
    })

    return jsonify({"response": respuesta})

# =====================================================
# RUN
# =====================================================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)