from flask import Flask, request, jsonify, send_from_directory
import os

app = Flask(__name__, static_folder="static")

# -------------------------------
# Home
# -------------------------------
@app.route("/")
def index():
    return send_from_directory(".", "index.html")

# -------------------------------
# Chat endpoint
# -------------------------------
@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    user_message = data.get("message", "")

    # Respuesta simple de prueba (reemplazable por OpenRouter luego)
    reply = f"Clon dice: {user_message}"

    return jsonify({"reply": reply})

# -------------------------------
# Render compatibility
# -------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
