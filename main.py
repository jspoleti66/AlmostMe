from flask import Flask, request, render_template, jsonify
import os
import requests

app = Flask(__name__)

# Leer archivos del contexto
def cargar_contexto():
    base_path = "data"
    archivos = {
        "configuracion": ["prompt_sistema.txt", "instrucciones_generales.txt"],
        "conocimientos": ["cv.txt", "documentos_tecnicos.txt", "respuestas_frecuentes.txt"],
        "datos_personales": ["historia_personal.txt", "intereses.txt", "personalidad.txt"],
        "fuentes_conversacionales": ["chats.txt", "emails.txt"],
        "proyectos": ["proyectos_actuales.txt", "tecnologias_utilizadas.txt"]
    }

    contexto = ""
    for carpeta, lista_archivos in archivos.items():
        for archivo in lista_archivos:
            ruta = os.path.join(base_path, carpeta, archivo)
            if os.path.exists(ruta):
                with open(ruta, "r", encoding="utf-8") as f:
                    contexto += f"\n### {archivo} ({carpeta})\n{f.read()}\n"
            else:
                print(f"⚠️ Archivo no encontrado: {ruta}")
    return contexto.strip()

# Consulta a OpenRouter
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
        "temperature": 0.7
    }

    response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload)
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

# Contexto inicial
contexto = cargar_contexto()
historial = [{
    "role": "system",
    "content": f"Eres un clon digital personalizado. Usa únicamente este contexto: {contexto}."
}]

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    user_input = request.json.get("message")
    historial.append({"role": "user", "content": user_input})
    respuesta = consultar_openrouter(historial)
    historial.append({"role": "assistant", "content": respuesta})
    return jsonify({"response": respuesta})

if __name__ == "__main__":
    # Render asigna un puerto en la variable de entorno PORT
    port = int(os.environ.get("PORT", 5000))
    # '0.0.0.0' es fundamental para que sea accesible externamente
    app.run(host='0.0.0.0', port=port)