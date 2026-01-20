import os
from flask import Flask, request, render_template, jsonify, session, send_from_directory, abort
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
    bloques = []
    if os.path.exists(base_path):
        for archivo in sorted(os.listdir(base_path)):
            ruta = os.path.join(base_path, archivo)
            if os.path.isfile(ruta):
                with open(ruta, "r", encoding="utf-8") as f:
                    bloques.append(f"[{archivo}]\n{f.read().strip()}")
    return "\n\n".join(bloques)

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
# GITHUB MODELS – LLAMA
# =====================================================

def consultar_github(historial):
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        return "⚠️ Error: GITHUB_TOKEN no configurado."

    endpoint = "https://models.inference.ai.azure.com"

    try:
        client = ChatCompletionsClient(
            endpoint=endpoint,
            credential=AzureKeyCredential(token),
        )

        mensajes = [SystemMessage(content=CONTEXTO_UNIFICADO)]

        # Ventana deslizante estricta
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

        return "⚠️ El modelo no devolvió una respuesta válida."

    except Exception as e:
        print(f"❌ ERROR GITHUB MODELS: {type(e).__name__} - {e}")
        return "⚠️ Error en la comunicación."

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
        return jsonify({"response": "⚠️ Error interno del servidor."}), 500

# =====================================================
# MANUALES INTERNOS (PDF)
# =====================================================

@app.route("/manuales/<path:filename>")
def manuales(filename):
    carpeta = os.path.join(app.root_path, "data", "manuales")

    # Seguridad básica
    if ".." in filename or filename.startswith("/"):
        abort(403)

    if not os.path.exists(os.path.join(carpeta, filename)):
        abort(404)

    return send_from_directory(carpeta, filename, as_attachment=False)

# =====================================================
# RUN
# =====================================================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
