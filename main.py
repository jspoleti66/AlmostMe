import json
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


# ---------------------------------------------------
# UTILIDADES
# ---------------------------------------------------

def load_text_file(relative_path: str) -> str:
    file_path = BASE_DIR / relative_path
    if not file_path.exists():
        return ""
    return file_path.read_text(encoding="utf-8").strip()


def load_json(relative_path: str):
    file_path = BASE_DIR / relative_path
    if not file_path.exists():
        return {}
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------
# CARGA DE CONFIGURACIÓN
# ---------------------------------------------------

context = load_json("context.json")

SYSTEM_PROMPT_PATH = context.get("system_prompt")
DOMAINS = context.get("domains", {})
HISTORY_LIMIT = context.get("history_limit", 6)


# ---------------------------------------------------
# CONSTRUCCIÓN DE HECHOS AUTORIZADOS
# ---------------------------------------------------

def build_facts_block() -> str:
    """
    Construye el bloque único de hechos autorizados
    combinando todos los dominios definidos en context.json.
    No hay hardcode.
    """

    domain_items = sorted(
        DOMAINS.items(),
        key=lambda x: x[1].get("priority", 0),
        reverse=True
    )

    collected_texts = []

    for domain_name, domain_data in domain_items:
        files = domain_data.get("files", [])

        for file_name in files:
            file_path = f"data/{file_name}"
            content = load_text_file(file_path)

            if content:
                collected_texts.append(content)

    return "\n\n".join(collected_texts).strip()


# ---------------------------------------------------
# CONSTRUCCIÓN DEL PROMPT FINAL
# ---------------------------------------------------

def build_prompt(user_message: str, conversation_history: list) -> list:
    """
    Devuelve lista de mensajes estilo OpenAI:
    [
        {"role": "system", "content": "..."},
        {"role": "user", "content": "..."}
    ]
    """

    system_text = load_text_file(SYSTEM_PROMPT_PATH)
    personality_text = load_text_file("data/personalidad.txt")
    facts_block = build_facts_block()

    unified_system_prompt = f"""
{system_text}

────────────────────────────────────────
HECHOS_AUTORIZADOS
────────────────────────────────────────

{facts_block if facts_block else "No hay hechos autorizados definidos."}

────────────────────────────────────────
PERSONALIDAD
────────────────────────────────────────

{personality_text}

Fin del contexto.
""".strip()

    messages = [
        {"role": "system", "content": unified_system_prompt}
    ]

    # Historial limitado solo para coherencia
    if conversation_history:
        for msg in conversation_history[-HISTORY_LIMIT:]:
            messages.append(msg)

    messages.append({"role": "user", "content": user_message})

    return messages
