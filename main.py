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
# PALABRAS CLAVE
# =====================================================

PALABRAS_RECURSOS = [
    "recurso", "recursos",
    "tutorial", "tutoriales",
    "guia", "guía",
    "curso", "cursos",
    "documentacion", "documentación",
    "material", "materiales"
]


PALABRAS_MANUALES = [
    "manual", "manuales", "abrir", "descargar"
]


# =====================================================
# CARGA
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

    data = {}

    if not os.path.exists(BASE_PATH):
        return data

    for f in os.listdir(BASE_PATH):

        name, ext = os.path.splitext(f)
        path = os.path.join(BASE_PATH, f)

        if ext == ".txt":

            c = cargar_txt(path)

            if c:
                data[name] = c


        elif ext == ".json" and f != "manuales.json":

            j = cargar_json(path)

            if j:
                data[name] = json.dumps(
                    j,
                    ensure_ascii=False,
                    indent=2
                )

    return data


def cargar_manuales():

    if not os.path.exists(MANUALES_PATH):
        return []

    with open(MANUALES_PATH, encoding="utf-8") as f:
        return json.load(f).get("items", [])



SYSTEM_PROMPT = cargar_txt(SYSTEM_PATH)
CONOCIMIENTO = cargar_conocimiento()
MANUALES = cargar_manuales()


# =====================================================
# CONTEXTO
# =====================================================

def construir_contexto():

    bloques = []

    for dom, cont in CONOCIMIENTO.items():

        bloques.append(
            "────────────────────────────────────────\n"
            f"DOMINIO: {dom}\n"
            "────────────────────────────────────────\n"
            f"{cont}"
        )

    return (
        f"{SYSTEM_PROMPT}\n\n"
        "════════════════════════════════════════\n"
        "CONOCIMIENTO PERSONAL AUTORIZADO\n"
        "════════════════════════════════════════\n\n"
        + "\n\n".join(bloques)
    )


# =====================================================
# MANUALES
# =====================================================

def buscar_manual(texto):

    t = texto.lower()

    for m in MANUALES:

        ids = m.get("id", "").lower().split(",")

        for i in ids:

            if i.strip() in t:
                return m

    return None


def generar_vcard(m):

    return f"""
<div class="vcard">
  <strong>{m['title']}</strong><br>
  <span>{m['summary']}</span><br>
  <a href="{m['url']}" target="_blank" rel="noopener">Abrir manual</a>
</div>
"""


# =====================================================
# MODELO
# =====================================================

def consultar_modelo(historial, msg):

    token = os.getenv("GITHUB_TOKEN")

    if not token:
        return "No tengo acceso al modelo."


    client = ChatCompletionsClient(
        endpoint="https://models.inference.ai.azure.com",
        credential=AzureKeyCredential(token),
    )


    mensajes = [
        SystemMessage(content=construir_contexto())
    ]


    for h in historial[-6:]:

        if h["role"] == "user":
            mensajes.append(UserMessage(content=h["content"]))

        elif h["role"] == "assistant":
            mensajes.append(AssistantMessage(content=h["content"]))


    mensajes.append(UserMessage(content=msg))


    r = client.complete(
        model="Meta-Llama-3.1-8B-Instruct",
        messages=mensajes,
        temperature=0.05,   # 🔑 menos fantasía
        max_tokens=400,
        top_p=0.05
    )

    return r.choices[0].message.content.strip()


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

        return jsonify(type="text", content="Decime.")


    historial = session["historial"]

    texto = mensaje.lower()


    # =============================================
    # MANUALES
    # =============================================

    if any(p in texto for p in PALABRAS_MANUALES):

        manual = buscar_manual(mensaje)

        if manual:

            html = generar_vcard(manual)

            historial += [
                {"role":"user","content":mensaje},
                {"role":"assistant","content":html}
            ]

            session["historial"] = historial[-12:]

            return jsonify(type="card", content=html)


        return jsonify(
            type="text",
            content="No tengo información sobre ese manual."
        )


    # =============================================
    # RECURSOS
    # =============================================

    if any(p in texto for p in PALABRAS_RECURSOS):

        return jsonify(
            type="text",
            content="No tengo información sobre esos recursos."
        )


    # =============================================
    # CHAT NORMAL
    # =============================================

    resp = consultar_modelo(historial, mensaje)


    historial += [
        {"role":"user","content":mensaje},
        {"role":"assistant","content":resp}
    ]


    session["historial"] = historial[-12:]


    return jsonify(type="text", content=resp)



# =====================================================
# RUN
# =====================================================

if __name__ == "__main__":

    port = int(os.environ.get("PORT", 5000))

    app.run(host="0.0.0.0", port=port)
