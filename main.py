import os
import json
from flask import Flask, request, jsonify, render_template, session
from datetime import timedelta

# =====================================================
# APP
# =====================================================

app = Flask(__name__)

app.secret_key = os.getenv("SECRET_KEY", "almostme_secret_2026")
app.permanent_session_lifetime = timedelta(minutes=30)

# =====================================================
# CARGA DE MANUALES (FUENTE ÚNICA DE VERDAD)
# data/manuales/*.json
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
# HELPERS
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
        "que manuales",
        "lista de manuales",
        "tenes manuales",
        "qué manuales guardas",
        "documentacion"
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
        "hay alguno más"
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
# RUTAS
# =====================================================

@app.route("/")
def index():
    session.permanent = True
    session.setdefault("historial", [])
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
        if not MANUALES:
            return jsonify({
                "type": "text",
                "text": "No tengo manuales internos disponibles."
            })

        return jsonify({
            "type": "manual_list",
            "manuales": MANUALES
        })

    # ============================
    # 2️⃣ BUSCAR MANUAL
    # ============================
    encontrados = buscar_manuales(mensaje)
    if encontrados:
        return jsonify({
            "type": "manual_list",
            "manuales": encontrados
        })

    # ============================
    # 3️⃣ PEDIDO DE “OTRO”
    # ============================
    if es_pedido_otro(mensaje):
        return jsonify({
            "type": "text",
            "text": "No tengo otros manuales además de los que ya te mostré."
        })

    # ============================
    # 4️⃣ FALLBACK CONTROLADO
    # ============================
    return jsonify({
        "type": "text",
        "text": "Puedo ayudarte con manuales internos o con consultas generales."
    })


# =====================================================
# RUN
# =====================================================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
