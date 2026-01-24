const chat = document.getElementById("chat");
const input = document.getElementById("userInput");
const sendBtn = document.getElementById("sendBtn");

let typingIndicator = null;
let isSending = false;

sendBtn.addEventListener("click", sendMessage);
input.addEventListener("keydown", e => {
  if (e.key === "Enter") sendMessage();
});

async function sendMessage() {
  if (isSending) return;

  const message = input.value.trim();
  if (!message) return;

  isSending = true;

  addMessage(message, "user");
  input.value = "";

  showTyping();

  try {
    const res = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message })
    });

    const data = await res.json();

    hideTyping();

    if (data.type === "card") {
      addMessageHTML(data.content, "bot");
    } else {
      addMessage(data.content, "bot");
    }

  } catch (err) {
    hideTyping();
    addMessage("⚠️ Error de conexión", "bot");
  }

  isSending = false;
}

/* ============================
   MENSAJES
============================ */

function addMessage(text, type) {
  const div = document.createElement("div");
  div.className = "msg " + type;
  div.textContent = text;

  chat.appendChild(div);
  scrollDown();
}

function addMessageHTML(html, type) {
  const div = document.createElement("div");
  div.className = "msg " + type;
  div.innerHTML = html;

  chat.appendChild(div);
  scrollDown();
}

/* ============================
   TYPING
============================ */

function showTyping() {
  if (typingIndicator) return;

  typingIndicator = document.createElement("div");
  typingIndicator.className = "msg bot typing";
  typingIndicator.innerHTML = `
    <span class="dots">
      <span>.</span><span>.</span><span>.</span>
    </span>
  `;

  chat.appendChild(typingIndicator);
  scrollDown();
}

function hideTyping() {
  if (typingIndicator) {
    typingIndicator.remove();
    typingIndicator = null;
  }
}

/* ============================
   UX
============================ */

function scrollDown() {
  chat.scrollTop = chat.scrollHeight;
}
