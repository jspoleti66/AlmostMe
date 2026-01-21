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

app.config.update(
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True
)

# =====================================================
# MANUALES INTERNOS (FUENTE ÚNICA DE VERDAD)
# Archivos físicos en: static/manuales/
# =====================================================

MANUALES_DISPONIBLES = {
    "piscina": {
        "titulo": "Manejo de la piscina",
        "archivo": "/static/manuales/piscina.pdf",
        "keywords": [
            "manual de la piscina",
            "manejo de la piscina",
            "mantenimiento de la piscina",
            "como limpiar la piscina",
            "manual piscina",
            "instrucciones piscina"
        ]
    }
}

# =====================================================
# HELPERS MANUALES
# =====================================================

def es_pedido_lista_manuales(texto: str) -> bool:
    texto = texto.lower()
    triggers = [
        "que manuales",
        "manuales disponibles",
        "tenes manuales",
        "documentacion",
        "manual interno"
    ]
    return any(t in texto for t in triggers)

def buscar_manual(texto: str):
    texto = texto.lower()
    for manual in MANUALES_DISPONIBLES.values():
        for kw in manual["keywords"]:
            if kw in texto:
                return manual
    return None

def existe_archivo_static(ruta_publica: str) -> bool:
    """
    Verifica que el archivo exista físicamente en /static
    """
    ruta = ruta_publica.replace("/static/", "")
    ruta_fisica = os.path.join(app.root_path, "static", ruta)
    return os.path.exists(ruta_fisica)

# =====================================================
# CARGA DE SYSTEM + CONOCIMIENTO
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
                data = json.load(f)
                texto += f"\n### {archivo}\n"
                texto += json.dumps(data, ensure_ascii=False, indent=2)

        elif archivo.endswith(".txt"):
            with open(ruta, "r", encoding="utf-8") as f:
                texto += f"\n### {archivo}\n{f.read().strip()}\n"

    return texto.strip()

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
# MODELO (GITHUB MODELS / LLAMA)
# =====================================================

def consultar_github(historial):
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        return "Error de configuración."

    endpoint = "https://models.inference.ai.azure.com"

    try:
        client = ChatCompletionsClient(
            endpoint=endpoint,
            credential=AzureKeyCredential(token),
        )

        mensajes = [SystemMessage(content=CONTEXTO_UNIFICADO)]

        for msg in historial[-6:]:
            if msg["role"] == "user":
                mensajes.append(UserMessage(content=msg["content"]))
            elif msg["role"] == "assistant":
                mensajes.append(AssistantMessage(content=msg["content"]))

        response = client.complete(
            model="Meta-Llama-3.1-8B-Instruct",
            messages=mensajes,
            temperature=0.20,
            max_tokens=384,
            top_p=0.1
        )

        if response and response.choices:
            return response.choices[0].message.content.strip()

        return "No tengo una respuesta para eso."

    except Exception as e:
        print(f"❌ ERROR MODELO: {e}")
        return "Error en la comunicación."

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
    try:
        data = request.get_json(force=True, silent=True)
        if not data or "message" not in data:
            return jsonify({"response": "Mensaje inválido."}), 400

        user_input = data["message"].strip()
        if not user_input:
            return jsonify({"response": "Decime algo para comenzar."})

        session.setdefault("historial", [])

        # =================================================
        # 1) LISTADO DE MANUALES
        # =================================================
        if es_pedido_lista_manuales(user_input):
            if not MANUALES_DISPONIBLES:
                return jsonify({"response": "No tengo manuales internos disponibles."})

            respuesta = "Tengo disponible el siguiente manual interno:\n"
            for m in MANUALES_DISPONIBLES.values():
                respuesta += f"- {m['titulo']}\n"

            return jsonify({"response": respuesta.strip()})

        # =================================================
        # 2) MANUAL ESPECÍFICO
        # =================================================
        manual = buscar_manual(user_input)
        if manual:
            if not existe_archivo_static(manual["archivo"]):
                return jsonify({
                    "response": "No tengo un manual interno disponible sobre ese tema."
                })

            return jsonify({
                "response": (
                    f"Tengo un manual interno sobre el manejo de la piscina.\n"
                    f"{manual['archivo']}"
                )
            })

        # =================================================
        # 3) RESTO → MODELO
        # =================================================
        session["historial"].append({
            "role": "user",
            "content": user_input
        })

        respuesta = consultar_github(session["historial"])

        session["historial"].append({
            "role": "assistant",
            "content": respuesta
        })

        session["historial"] = session["historial"][-12:]
        session.modified = True

        return jsonify({"response": respuesta})

    except Exception as e:
        print(f"❌ ERROR /chat: {e}")
        return jsonify({"response": "Error interno del servidor."}), 500

# =====================================================
# RUN
# =====================================================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
