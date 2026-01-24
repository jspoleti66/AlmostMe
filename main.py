from flask import Flask, request, jsonify
import json

app = Flask(__name__)

# ───────────────────────────────────────
# Cargar manuales
# ───────────────────────────────────────
with open("manuales.json", "r", encoding="utf-8") as f:
    MANUALES = json.load(f)["items"]


def buscar_manual(texto):
    texto = texto.lower()
    for manual in MANUALES:
        if manual["id"] in texto or manual["title"].lower() in texto:
            return manual
    return None


def render_manual_vcard(manual):
    return f"""
<div class="vcard">
  <strong>📘 {manual['title']}</strong><br>
  <span>{manual['summary']}</span><br>
  <a href="{manual['url']}" target="_blank" rel="noopener">Abrir manual</a>
</div>
""".strip()


@app.route("/chat", methods=["POST"])
def chat():
    user_message = request.json.get("message", "").lower()

    manual = buscar_manual(user_message)
    if manual:
        return jsonify({
            "type": "card",
            "content": render_manual_vcard(manual)
        })

    return jsonify({
        "type": "text",
        "content": "No tengo información sobre eso."
    })


if __name__ == "__main__":
    app.run(debug=True)
