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

MODO_GENERAL = "general"
MODO_MANUALES = "manuales"

# =====================================================
# CARGA DE MANUALES
# =====================================================

def cargar_manuales():
    base_path = "data/manuales"
    manuales = []

    if not os.path.exists(base_path):
        return manuales

    for archivo in os.listdir(base_path):
        if archivo.endswith(".json"):
            with open(os.path.join(base_path, archivo), encoding="utf-8") as f:
                data = json.load(f)
                manuales.append({
                    "id": data["id"],
                    "titulo": data["titulo"],
                    "descripcion": data.get("descripcion", ""),
                    "disparadores": data.get("disparadores", []),
                    "link": f"/static/manuales/{data['id']}.pdf"
                })

    return manuales


MANUALES = cargar_manuales()

# =====================================================
# HELPERS MANUALES
# =====================================================

def buscar_manuales(texto):
    texto = texto.lower()
    return [
        m for m in MANUALES
        if any(d in texto for d in m.get("disparadores", []))
    ]


def es_pedido_lista(texto):
    texto = texto.lower()
    return any(t in texto for t in [
        "manuales",
        "qué manuales",
        "que manuales",
        "lista de manuales",
        "tenes manuales",
        "documentacion",
        "documentación"
    ])


def es_pedido_otro(texto):
    return texto.lower().strip() in [
        "otro",
        "y otro",
        "y que otro",
        "algún otro",
        "algun otro",
        "otro manual",
        "hay otro",
        "hay alguno más",
        "hay alguno mas"
    ]


def es_salida_manual(texto):
    return texto.lower().strip() in [
        "ok",
        "gracias",
        "listo",
        "perfecto",
        "cambiemos de tema",
        "otra cosa"
    ]

# =====================================================
# SYSTEM + CONOCIMIENTO
# =====================================================

def cargar_system_prompt():
    ruta = "data/prompts/system.txt"
    return open(ruta, encoding="utf-8").read() if os.path.exists(ruta) else ""


def cargar_conocimiento():
    base_path = "data/conocimiento"
    bloques = []

    if not os.path.exists(base_path):
        return ""

    for archivo in sorted(os.listdir(base_path)):
        if archivo.endswith(".txt"):
            with open(os.path.join(base_path, archivo), encoding="utf-8") as f:
                contenido = f.read().strip()
                if contenido:
                    bloques.append(f"### {archivo}\n{contenido}")

    return "\n\n".join(bloques)


SYSTEM_PROMPT = cargar_system_prompt()
CONOCIMIENTO = cargar_conocimiento()

# =====================================================
# MODELO (GitHub)
# =====================================================

def consultar_modelo(system_prompt, conocimiento, historial, mensaje_usuario):
    api_key = os.getenv("GITHUB_TOKEN")
    if not api_key:
        return "No tengo acceso al modelo en este momento."

    url = "https://models.inference.ai.azure.com/chat/completions"

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "system", "content": f"CONOCIMIENTO DISPONIBLE:\n\n{conocimiento}"}
    ]

    messages.extend(historial)
    messages.append({"role": "user", "content": mensaje_usuario})

    payload = {
        "model": "gpt-4o-mini",
        "messages": messages,
        "temperature": 0.2
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
    session.setdefault("modo", MODO_GENERAL)
    return render_template("index.html")


@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True)
    mensaje = data.get("message", "").strip()

    if not mensaje:
        return jsonify({"type": "text", "text": "Decime algo para comenzar."})

    # ============================
    # ENTRADA A MANUALES
    # ============================

    if es_pedido_lista(mensaje):
        session["modo"] = MODO_MANUALES
        session["manuales_mostrados"] = MANUALES
        return jsonify({"type": "manual_list", "manuales": MANUALES})

    encontrados = buscar_manuales(mensaje)
    if encontrados:
        session["modo"] = MODO_MANUALES
        session["manuales_mostrados"] = encontrados
        return jsonify({"type": "manual_list", "manuales": encontrados})

    # ============================
    # MODO MANUALES (BACKEND PURO)
    # ============================

    if session.get("modo") == MODO_MANUALES:

        if es_pedido_otro(mensaje):
            ya = session.get("manuales_mostrados", [])
            restantes = [m for m in MANUALES if m not in ya]

            if restantes:
                session["manuales_mostrados"] = restantes
                return jsonify({"type": "manual_list", "manuales": restantes})

            return jsonify({
                "type": "text",
                "text": "No hay otros manuales disponibles."
            })

        if es_salida_manual(mensaje):
            session["modo"] = MODO_GENERAL
            return jsonify({
                "type": "text",
                "text": "Perfecto. ¿En qué más te puedo ayudar?"
            })

        # 🔒 BLOQUEO TOTAL AL MODELO
        return jsonify({
            "type": "text",
            "text": "Si querés otro manual decime “otro”, o decime “ok” para seguir con otra cosa."
        })

    # ============================
    # CONVERSACIÓN GENERAL
    # ============================

    historial = session.get("historial", [])
    respuesta = consultar_modelo(SYSTEM_PROMPT, CONOCIMIENTO, historial, mensaje)

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
