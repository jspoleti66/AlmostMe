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
app.secret_key = os.getenv("SECRET_KEY", "almostme_secret_2026")
app.permanent_session_lifetime = timedelta(minutes=30)

# =====================================================
# CARGA DE CONOCIMIENTO (MODELO)
# =====================================================

def cargar_system_prompt():
    ruta = "data/prompts/system.txt"
    if os.path.exists(ruta):
        with open(ruta, encoding="utf-8") as f:
            return f.read().strip()
    return ""

def cargar_conocimiento():
    base_path = "data/conocimiento"
    bloques = []

    if not os.path.exists(base_path):
        return ""

    for archivo in sorted(os.listdir(base_path)):
        ruta = os.path.join(base_path, archivo)
        if archivo.endswith(".txt") or archivo.endswith(".json"):
            with open(ruta, encoding="utf-8") as f:
                bloques.append(f"\n### {archivo}\n{f.read().strip()}")

    return "\n".join(bloques)

SYSTEM_PROMPT = cargar_system_prompt()
CONOCIMIENTO = cargar_conocimiento()

SYSTEM_COMPLETO = f"""
{SYSTEM_PROMPT}

────────────────────────────────────────
CONOCIMIENTO DEFINIDO
────────────────────────────────────────
{CONOCIMIENTO}
""".strip()

# =====================================================
# CARGA DE MANUALES (BACKEND – FUENTE ÚNICA)
# =====================================================

def cargar_manuales():
    base_path = "data/manuales"
    manuales = []

    if not os.path.exists(base_path):
        return manuales

    for archivo in os.listdir(base_path):
        if archivo.endswith(".json"):
            with open(os.path.join(base_path, archivo), encoding="utf-8") as f:
                manuales.append(json.load(f))

    return manuales

MANUALES = cargar_manuales()

# =====================================================
# HELPERS MANUALES
# =====================================================

def buscar_manuales(texto: str):
    texto = texto.lower()
    encontrados = []

    for manual in MANUALES:
        for disparador in manual.get("disparadores", []):
            if disparador in texto:
                encontrados.append(manual)
                break

    return encontrados

def es_pedido_lista(texto: str) -> bool:
    texto = texto.lower()
    triggers = [
        "manuales",
        "qué manuales",
        "que manuales",
        "lista de manuales",
        "tenes manuales",
        "documentacion",
        "documentación"
    ]
    return any(t in texto for t in triggers)

def es_pedido_otro(texto: str) -> bool:
    texto = texto.lower().strip()
    return texto in [
        "otro",
        "algún otro",
        "algun otro",
        "otro manual",
        "algún otro manual",
        "hay otro",
        "hay alguno más",
        "hay alguno mas"
    ]

# =====================================================
# MODELO (GITHUB MODELS)
# =====================================================

def consultar_modelo(historial, mensaje_usuario):
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        return "No tengo acceso al modelo en este momento."

    client = ChatCompletionsClient(
        endpoint="https://models.inference.ai.azure.com",
        credential=AzureKeyCredential(token)
    )

    mensajes = [SystemMessage(content=SYSTEM_COMPLETO)]

    for h in historial[-6:]:
        if h["role"] == "user":
            mensajes.append(UserMessage(content=h["content"]))
        elif h["role"] == "assistant":
            mensajes.append(AssistantMessage(content=h["content"]))

    mensajes.append(UserMessage(content=mensaje_usuario))

    try:
        response = client.complete(
            model="Meta-Llama-3.1-8B-Instruct",
            messages=mensajes,
            temperature=0.25,
            max_tokens=400,
            top_p=0.1
        )
        return response.choices[0].message.content.strip()
    except Exception:
        return "No pude responder en este momento."

# =====================================================
# RUTAS
# =====================================================

@app.route("/")
def index():
    session.permanent = True
    session.setdefault("historial", [])
    session.setdefault("manuales_mostrados", [])
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True)
    if not data or "message" not in data:
        return jsonify({"type": "text", "text": "Mensaje inválido."})

    mensaje = data["message"].strip()
    if not mensaje:
        return jsonify({"type": "text", "text": "Decime algo para comenzar."})

    # 1️⃣ LISTA DE MANUALES
    if es_pedido_lista(mensaje):
        session["manuales_mostrados"] = MANUALES
        return jsonify({"type": "manual_list", "manuales": MANUALES})

    # 2️⃣ BUSCAR MANUAL
    encontrados = buscar_manuales(mensaje)
    if encontrados:
        session["manuales_mostrados"] = encontrados
        return jsonify({"type": "manual_list", "manuales": encontrados})

    # 3️⃣ PEDIDO DE “OTRO”
    if es_pedido_otro(mensaje):
        ya = session.get("manuales_mostrados", [])
        restantes = [m for m in MANUALES if m not in ya]
        if restantes:
            session["manuales_mostrados"] = restantes
            return jsonify({"type": "manual_list", "manuales": restantes})
        return jsonify({"type": "text", "text": "No hay otros manuales disponibles."})

    # 4️⃣ MODELO
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
