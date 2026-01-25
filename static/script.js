const input = document.getElementById("userInput");
const button = document.getElementById("sendBtn");
const chat = document.getElementById("chat");

/* Send */

button.addEventListener("click", sendMessage);
input.addEventListener("keypress", e => {
  if (e.key === "Enter") sendMessage();
});

/* Main */

async function sendMessage() {

  const message = input.value.trim();
  if (!message) return;

  addUser(message);
  input.value = "";

  const res = await fetch("/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message })
  });

  const data = await res.json();

  addBot(data);
}

/* UI */

function addUser(text) {

  const div = document.createElement("div");
  div.className = "message user";
  div.textContent = text;

  chat.appendChild(div);
  scroll();
}

function addBot(data) {

  const div = document.createElement("div");
  div.className = "message bot";

  if (data.type === "card") {
    div.innerHTML = data.content;
  } else {
    div.textContent = data.content;
  }

  chat.appendChild(div);
  scroll();
}

/* Scroll */

function scroll() {
  chat.scrollTop = chat.scrollHeight;
}
