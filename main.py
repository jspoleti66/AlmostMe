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
# CARGA DE MANUALES
# Fuente única: data/manuales/*.json
# PDFs: /static/manuales/<id>.pdf
# =====================================================

def cargar_manuales():
    base_path = "data/manuales"
    manuales = []

    if not os.path.exists(base_path):
        return manuales

    for archivo in os.listdir(base_path):
        if not archivo.endswith(".json"):
            continue

        with open(os.path.join(base_path, archivo), encoding="utf-8") as f:
            data = json.load(f)

            manual = {
                "id": data["id"],
                "titulo": data["titulo"],
                "descripcion": data.get("descripcion", ""),
                "disparadores": data.get("disparadores", []),
                "link": f"/static/manuales/{data['id']}.pdf"
            }

            manuales.append(manual)

    return manuales


MANUALES = cargar_manuales()

# =====================================================
# HELPERS MANUALES
# =====================================================

def buscar_manuales(texto: str):
    texto = texto.lower()
    encontrados = []

    for manual in MANUALES:
        for d in manual.get("disparadores", []):
            if d in texto:
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
        "algún otro manual",
        "otro manual",
        "hay otro",
        "hay alguno más",
        "hay alguno mas"
    ]


# =====================================================
# SYSTEM PROMPT
# =====================================================

def cargar_system_prompt():
    ruta = "data/prompts/system.txt"
    if os.path.exists(ruta):
        with open(ruta, encoding="utf-8") as f:
            return f.read()
    return ""

SYSTEM_PROMPT = cargar_system_prompt()

# =====================================================
# MODELO (GitHub / OpenAI compatible)
# =====================================================

def consultar_modelo(system_prompt, historial, mensaje_usuario):
    api_key = os.getenv("GITHUB_TOKEN")
    if not api_key:
        return "No tengo acceso al modelo en este momento."

    url = "https://models.inference.ai.azure.com/chat/completions"

    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(historial)
    messages.append({"role": "user", "content": mensaje_usuario})

    payload = {
        "model": "gpt-4o-mini",
        "messages": messages,
        "temperature": 0.3
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    try:
        r = requests.post(url, headers=headers, json=payload, timeout=30)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip()
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

    # ============================
    # 1️⃣ LISTA DE MANUALES
    # ============================
    if es_pedido_lista(mensaje):
        session["manuales_mostrados"] = MANUALES
        return jsonify({
            "type": "manual_list",
            "manuales": MANUALES
        })

    # ============================
    # 2️⃣ BUSCAR MANUAL
    # ============================
    encontrados = buscar_manuales(mensaje)
    if encontrados:
        session["manuales_mostrados"] = encontrados
        return jsonify({
            "type": "manual_list",
            "manuales": encontrados
        })

    # ============================
    # 3️⃣ PEDIDO DE “OTRO”
    # ============================
    if es_pedido_otro(mensaje):
        ya = session.get("manuales_mostrados", [])
        restantes = [m for m in MANUALES if m not in ya]

        if restantes:
            session["manuales_mostrados"] = restantes
            return jsonify({
                "type": "manual_list",
                "manuales": restantes
            })

        return jsonify({
            "type": "text",
            "text": "No hay otros manuales disponibles."
        })

    # ============================
    # 4️⃣ CONVERSACIÓN GENERAL
    # ============================
    historial = session.get("historial", [])

    respuesta = consultar_modelo(
        system_prompt=SYSTEM_PROMPT,
        historial=historial,
        mensaje_usuario=mensaje
    )

    historial.append({"role": "user", "content": mensaje})
    historial.append({"role": "assistant", "content": respuesta})
    session["historial"] = historial[-12:]

    return jsonify({
        "type": "text",
        "text": respuesta
    })


# =====================================================
# RUN
# =====================================================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
