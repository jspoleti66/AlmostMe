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
SYSTEM_PATH = "data/prompts/system.txt"
MANUALES_PATH = "data/conocimiento/manuales.json"


# =====================================================
# CARGA DE ARCHIVOS
# =====================================================

def cargar_txt(path):

    if not os.path.exists(path):
        return ""

    with open(path, encoding="utf-8") as f:
        return f.read().strip()


def cargar_json(path):

    if not os.path.exists(path):
        return {}

    with open(path, encoding="utf-8") as f:
        return json.load(f)


def cargar_conocimiento():

    conocimiento = {}

    if not os.path.exists(BASE_PATH):
        return conocimiento

    for archivo in os.listdir(BASE_PATH):

        nombre, ext = os.path.splitext(archivo)
        ruta = os.path.join(BASE_PATH, archivo)

        if ext == ".txt":

            contenido = cargar_txt(ruta)

            if contenido:
                conocimiento[nombre] = contenido


        elif ext == ".json" and archivo != "manuales.json":

            data = cargar_json(ruta)

            if data:
                conocimiento[nombre] = json.dumps(
                    data,
                    ensure_ascii=False,
                    indent=2
                )

    return conocimiento


def cargar_manuales():

    if not os.path.exists(MANUALES_PATH):
        return []

    with open(MANUALES_PATH, encoding="utf-8") as f:
        data = json.load(f)

    return data.get("items", [])


SYSTEM_PROMPT = cargar_txt(SYSTEM_PATH)
CONOCIMIENTO = cargar_conocimiento()
MANUALES = cargar_manuales()


# =====================================================
# CONTEXTO GLOBAL
# =====================================================

def construir_contexto():

    bloques = []

    for dominio, contenido in CONOCIMIENTO.items():

        bloques.append(
            f"DOMINIO: {dominio}\n{contenido}"
        )

    return (
        f"{SYSTEM_PROMPT}\n\n"
        "CONOCIMIENTO PERSONAL:\n\n"
        + "\n\n".join(bloques)
    )


# =====================================================
# MODELO
# =====================================================

def cliente_modelo():

    token = os.getenv("GITHUB_TOKEN")

    if not token:
        return None

    return ChatCompletionsClient(
        endpoint="https://models.inference.ai.azure.com",
        credential=AzureKeyCredential(token),
    )


def llamar_modelo(mensajes):

    client = cliente_modelo()

    if not client:
        return "No tengo acceso al modelo."

    response = client.complete(
        model="Meta-Llama-3.1-8B-Instruct",
        messages=mensajes,
        temperature=0.2,
        max_tokens=600,
        top_p=0.2
    )

    return response.choices[0].message.content.strip()


# =====================================================
# INTENCIÓN
# =====================================================

def detectar_intencion(mensaje):

    prompt = f"""
Clasificá la intención del usuario.

Opciones:
- manual
- informacion
- chat

Respondé SOLO en JSON.

Mensaje:
"{mensaje}"
"""

    mensajes = [
        SystemMessage(content="Sos un clasificador."),
        UserMessage(content=prompt)
    ]

    salida = llamar_modelo(mensajes)

    try:
        data = json.loads(salida)
        return data.get("intent", "chat")
    except:
        return "chat"


# =====================================================
# MANUALES
# =====================================================

def buscar_manual_semantico(mensaje):

    texto = mensaje.lower()

    for manual in MANUALES:

        ids = manual.get("id", "").lower().split(",")

        for palabra in ids:

            if palabra.strip() in texto:
                return manual

    return None


def generar_vcard(manual):

    return f"""
<div class="vcard">
  <strong>{manual['title']}</strong><br>
  <span>{manual['summary']}</span><br>
  <a href="{manual['url']}" target="_blank">Abrir manual</a>
</div>
"""


# =====================================================
# CHAT IA
# =====================================================

def procesar_chat(historial, mensaje):

    mensajes = [
        SystemMessage(content=construir_contexto())
    ]

    for msg in historial[-6:]:

        if msg["role"] == "user":
            mensajes.append(UserMessage(content=msg["content"]))

        if msg["role"] == "assistant":
            mensajes.append(AssistantMessage(content=msg["content"]))

    mensajes.append(UserMessage(content=mensaje))

    return llamar_modelo(mensajes)


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

        return jsonify({
            "type": "text",
            "content": "Decime."
        })


    historial = session.get("historial", [])


    # ============================================
    # DETECTAR INTENCIÓN
    # ============================================

    intent = detectar_intencion(mensaje)


    # ============================================
    # MANUALES
    # ============================================

    if intent == "manual":

        manual = buscar_manual_semantico(mensaje)

        if manual:

            html = generar_vcard(manual)

            historial.extend([
                {"role": "user", "content": mensaje},
                {"role": "assistant", "content": html}
            ])

            session["historial"] = historial[-12:]

            return jsonify({
                "type": "card",
                "content": html
            })


    # ============================================
    # CHAT NORMAL
    # ============================================

    respuesta = procesar_chat(historial, mensaje)

    historial.extend([
        {"role": "user", "content": mensaje},
        {"role": "assistant", "content": respuesta}
    ])

    session["historial"] = historial[-12:]

    return jsonify({
        "type": "text",
        "content": respuesta
    })


# =====================================================
# RUN
# =====================================================

if __name__ == "__main__":

    port = int(os.environ.get("PORT", 5000))

    app.run(
        host="0.0.0.0",
        port=port,
        debug=True
    )
