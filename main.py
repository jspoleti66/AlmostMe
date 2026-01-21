import os
import json
from flask import Flask, request, render_template, jsonify, session
from azure.ai.inference import ChatCompletionsClient
from azure.ai.inference.models import SystemMessage, UserMessage, AssistantMessage
from azure.core.credentials import AzureKeyCredential
from datetime import timedelta

# =====================================================
# APP
# =====================================================

app = Flask(__name__)

# =====================================================
# CONFIGURACIÓN DE SESIÓN
# =====================================================

app.secret_key = os.getenv("SECRET_KEY", "almostme_secret_2026")
app.permanent_session_lifetime = timedelta(minutes=30)

# =====================================================
# MANUALES INTERNOS (ÚNICA FUENTE DE VERDAD)
# Archivos físicos en: static/manuales/
# =====================================================

MANUALES_DISPONIBLES = {
    "piscina": {
        "id": "piscina",
        "titulo": "Manejo de la piscina",
        "archivo": "/static/manuales/piscina.pdf",
        "keywords": [
            "piscina",
            "manual piscina",
            "manejo de la piscina",
            "mantenimiento de la piscina",
            "limpiar la piscina"
        ]
    }
}

# =====================================================
# HELPERS
# =====================================================

def es_pedido_lista_manuales(texto: str) -> bool:
    texto = texto.lower()
    return any(p in texto for p in [
        "manuales",
        "documentacion",
        "guias",
        "estoy buscando manual",
        "tenes manuales"
    ])

def buscar_manual(texto: str):
    texto = texto.lower()
    for manual in MANUALES_DISPONIBLES.values():
        if any(k in texto for k in manual["keywords"]):
            return manual
    return None

def existe_archivo_static(ruta_publica: str) -> bool:
    ruta = ruta_publica.replace("/static/", "")
    ruta_fisica = os.path.join(app.root_path, "static", ruta)
    return os.path.exists(ruta_fisica)

# =====================================================
# SYSTEM + CONOCIMIENTO
# =====================================================

def cargar_system_prompt():
    ruta = "data/prompts/system.txt"
    if os.path.exists(ruta):
        with open(ruta, "r", encoding="utf-8") as f:
            return f.read().strip()
    return "Sos AlmostMe, el clon digital conversacional de Juan."

def cargar_conocimiento():
    base_path = "data/conocimiento"
    texto = ""

    if not os.path.exists(base_path):
        return texto

    for archivo in sorted(os.listdir(base_path)):
        ruta = os.path.join(base_path, archivo)

        if archivo.endswith(".json"):
            with open(ruta, "r", encoding="utf-8") as f:
                texto += json.dumps(json.load(f), ensure_ascii=False, indent=2)

    return texto

SYSTEM_PROMPT = cargar_system_prompt()
CONOCIMIENTO = cargar_conocimiento()

CONTEXTO_UNIFICADO = f"""
{SYSTEM_PROMPT}

────────────────────────────────────────
CONOCIMIENTO BASE DEFINIDO
────────────────────────────────────────

{CONOCIMIENTO}
""".strip()

# =====================================================
# MODELO
# =====================================================

def consultar_modelo(historial):
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        return "Error de configuración."

    client = ChatCompletionsClient(
        endpoint="https://models.inference.ai.azure.com",
        credential=AzureKeyCredential(token)
    )

    mensajes = [SystemMessage(content=CONTEXTO_UNIFICADO)]

    for m in historial[-6:]:
        if m["role"] == "user":
            mensajes.append(UserMessage(content=m["content"]))
        else:
            mensajes.append(AssistantMessage(content=m["content"]))

    response = client.complete(
        model="Meta-Llama-3.1-8B-Instruct",
        messages=mensajes,
        temperature=0.2,
        max_tokens=384,
        top_p=0.1
    )

    return response.choices[0].message.content.strip()

# =====================================================
# RUTAS
# =====================================================

@app.route("/")
def index():
    session.setdefault("historial", [])
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    texto = data.get("message", "").strip().lower()

    # 1️⃣ LISTADO DE MANUALES
    if es_pedido_lista_manuales(texto):
        return jsonify({
            "type": "manual_list",
            "manuales": [
                {
                    "id": m["id"],
                    "titulo": m["titulo"]
                } for m in MANUALES_DISPONIBLES.values()
            ]
        })

    # 2️⃣ MANUAL ESPECÍFICO
    manual = buscar_manual(texto)
    if manual:
        if existe_archivo_static(manual["archivo"]):
            return jsonify({
                "type": "manual",
                "manual": {
                    "titulo": manual["titulo"],
                    "url": manual["archivo"]
                }
            })
        else:
            return jsonify({
                "type": "text",
                "text": "El manual existe pero el archivo no está disponible."
            })

    # 3️⃣ MENCIÓN DE TEMA NO DISPONIBLE
    if any(p in texto for p in ["piscina", "jardineria", "riego"]):
        return jsonify({
            "type": "text",
            "text": "No tengo un manual interno sobre ese tema."
        })

    # 4️⃣ MODELO
    session["historial"].append({"role": "user", "content": texto})
    respuesta = consultar_modelo(session["historial"])
    session["historial"].append({"role": "assistant", "content": respuesta})

    return jsonify({
        "type": "text",
        "text": respuesta
    })

# =====================================================
# RUN
# =====================================================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
