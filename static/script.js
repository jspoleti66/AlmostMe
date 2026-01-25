// ==============================
// FUNCIÓN PRINCIPAL DE ENVÍO
// ==============================
async function sendMessage() {
  const input = document.getElementById("userInput");
  const message = input.value.trim();
  if (!message) return;

  addUserMessage(message);
  input.value = "";

  // ==========================
  // MOSTRAR “typing” (...)
  // ==========================
  const chat = document.getElementById("chat");
  const typingDiv = document.createElement("div");
  typingDiv.className = "bot-message typing";
  typingDiv.textContent = "...";
  chat.appendChild(typingDiv);
  chat.scrollTop = chat.scrollHeight;

  try {
    const res = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message })
    });

    const data = await res.json();

    // ==========================
    // REEMPLAZAR TIPO DE MENSAJE
    // ==========================
    typingDiv.remove();
    addBotMessage(data);

  } catch (err) {
    typingDiv.remove();
    addBotMessage({ type: "text", content: "Error de conexión." });
  }
}

// ==============================
// FUNCIONES AUXILIARES
// ==============================
function addUserMessage(text) {
  const chat = document.getElementById("chat");
  const div = document.createElement("div");
  div.className = "user-message";
  div.textContent = text;
  chat.appendChild(div);
  chat.scrollTop = chat.scrollHeight;
}

function addBotMessage(response) {
  const chat = document.getElementById("chat");
  const div = document.createElement("div");
  div.className = "bot-message";

  if (response.type === "card") {
    div.innerHTML = response.content;
  } else {
    div.textContent = response.content;
  }

  chat.appendChild(div);
  chat.scrollTop = chat.scrollHeight;
}

// ==============================
// EVENTOS
// ==============================
document.getElementById("sendBtn").addEventListener("click", sendMessage);
document.getElementById("userInput").addEventListener("keypress", function(e) {
  if (e.key === "Enter") sendMessage();
});
