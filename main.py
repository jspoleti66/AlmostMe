import os
import json
from flask import Flask, request, jsonify, render_template, session
from datetime import timedelta

from azure.ai.inference import ChatCompletionsClient
from azure.ai.inference.models import SystemMessage, UserMessage, AssistantMessage
from azure.core.credentials import AzureKeyCredential

# =====================================================
# APP
# =====================================================

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "almostme_secret")
app.permanent_session_lifetime = timedelta(minutes=30)

BASE_PATH = "data/conocimiento"

# =====================================================
# LOADERS GENÉRICOS
# =====================================================

def cargar_txt(path):
    return open(path, encoding="utf-8").read().strip() if os.path.exists(path) else ""

def cargar_json(path):
    return json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {}

def cargar_dominios():
    config = cargar_json("data/domains.json")
    data = {}

    for dominio, cfg in config.items():
        path = os.path.join(BASE_PATH, cfg["file"])
        if cfg.get("type") == "json":
            data[dominio] = cargar_json(path)
        else:
            data[dominio] = cargar_txt(path)

    return config, data

DOMINIOS_CONFIG, DOMINIOS_DATA = cargar_dominios()

# =====================================================
# CONTEXTO BASE
# =====================================================

SYSTEM_PROMPT = cargar_txt("data/prompts/system.txt")

def detectar_dominio(mensaje):
    texto = mensaje.lower()
    for dominio, cfg in DOMINIOS_CONFIG.items():
        for kw in cfg.get("keywords", []):
            if kw in texto:
                return dominio
    return None

def construir_contexto(mensaje):
    dominio = detectar_dominio(mensaje)

    if dominio and dominio in DOMINIOS_DATA:
        contenido = DOMINIOS_DATA[dominio]
        return f"""
{SYSTEM_PROMPT}

────────────────────────────────────────
CONOCIMIENTO DEL DOMINIO: {dominio}
────────────────────────────────────────

{json.dumps(contenido, ensure_ascii=False, indent=2) if isinstance(contenido, dict) else contenido}
""".strip()

    # fallback minimal
    return SYSTEM_PROMPT

# =====================================================
# MODELO
# =====================================================

def consultar_modelo(historial, mensaje_usuario):
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        return "Error de configuración del modelo."

    contexto = construir_contexto(mensaje_usuario)

    client = ChatCompletionsClient(
        endpoint="https://models.inference.ai.azure.com",
        credential=AzureKeyCredential(token),
    )

    mensajes = [SystemMessage(content=contexto)]

    for msg in historial[-6:]:
        cls = UserMessage if msg["role"] == "user" else AssistantMessage
        mensajes.append(cls(content=msg["content"]))

    mensajes.append(UserMessage(content=mensaje_usuario))

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
        print("❌ ERROR MODELO:", e)
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
    data = request.get_json(silent=True) or {}
    mensaje = data.get("message", "").strip()

    if not mensaje:
        return jsonify({"type": "text", "text": "Decime algo para empezar."})

    historial = session.get("historial", [])
    respuesta = consultar_modelo(historial, mensaje)

    historial.extend([
        {"role": "user", "content": mensaje},
        {"role": "assistant", "content": respuesta}
    ])

    session["historial"] = historial[-12:]
    return jsonify({"type": "text", "text": respuesta})

# =====================================================
# RUN
# =====================================================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
