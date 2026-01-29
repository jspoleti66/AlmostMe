# ===============================
# INTENT
# ===============================

def mentions_manual_intent(text):

    triggers = [
        "manual",
        "manuales",
        "manueles",   # typo frecuente
        "guia",
        "guias",
        "instructivo",
        "documento",
        "documentacion",
        "instrucciones",
        "comparte",
        "compartir"
    ]

    t = normalize(text)

    return any(k in t for k in triggers)


def is_manual_list_question(text):

    t = normalize(text)

    patterns = [
        "que manuales",
        "que manueles",
        "cuales manuales",
        "que guias",
        "que documentos",
        "que tienes en manual",
        "que tenes en manual"
    ]

    return any(p in t for p in patterns)


# =====================================================
# ROUTES
# =====================================================

@app.route("/chat", methods=["POST"])
def chat():

    try:

        data = request.get_json(silent=True) or {}

        message = data.get("message", "").strip()

        if not message:

            return jsonify({
                "type": "text",
                "content": "Decime."
            })


        history = session.get("history", [])

        norm = normalize(message)


        # ===============================
        # BLOQUEO META
        # ===============================

        meta_triggers = [
            "que informacion guard",
            "que datos guard",
            "que sabes",
            "como funcionas",
            "tu memoria",
            "tu conocimiento",
            "que archivos"
        ]

        if any(k in norm for k in meta_triggers):

            return jsonify({
                "type": "text",
                "content": "No tengo información sobre eso."
            })


        # ===============================
        # MANUAL ESPECÍFICO (TOP PRIORITY)
        # ===============================

        manual = find_manual(message)

        if manual:

            card = render_vcard(manual)

            history.extend([
                {"role": "user", "content": message},
                {"role": "assistant", "content": card}
            ])

            session["history"] = history[-12:]

            return jsonify({
                "type": "card",
                "content": card
            })


        # ===============================
        # LISTA DE MANUALES (CERRADA)
        # ===============================

        if is_manual_list_question(message) or mentions_manual_intent(message):

            titles = list_manual_titles()

            if not titles:

                return jsonify({
                    "type": "text",
                    "content": "No tengo manuales."
                })

            txt = "Tengo estos manuales:\n\n"

            for t in titles:
                txt += f"• {t}\n"

            return jsonify({
                "type": "text",
                "content": txt.strip()
            })


        # ===============================
        # LISTA AMBIGUA
        # ===============================

        if "lista" in norm and "manual" not in norm:

            return jsonify({
                "type": "text",
                "content": "¿Lista de qué exactamente?"
            })


        # ===============================
        # MODELO
        # ===============================

        answer = query_model(history, message)

        history.extend([
            {"role": "user", "content": message},
            {"role": "assistant", "content": answer}
        ])

        session["history"] = history[-12:]


        return jsonify({
            "type": "text",
            "content": answer
        })


    except Exception as e:

        print("CHAT ERROR:", e)
        traceback.print_exc()

        return jsonify({
            "type": "text",
            "content": "Ocurrió un error interno."
        })
