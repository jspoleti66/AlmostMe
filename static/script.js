async function sendMessage() {
  const input = document.getElementById("userInput");
  const message = input.value.trim();
  if (!message) return;

  addUserMessage(message);
  input.value = "";

  const res = await fetch("/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message })
  });

  const data = await res.json();
  addBotMessage(data);
}

function addUserMessage(text) {
  const chat = document.getElementById("chat");
  const div = document.createElement("div");
  div.className = "user-message";
  div.textContent = text;
  chat.appendChild(div);
}

function addBotMessage(response) {
  const chat = document.getElementById("chat");
  const div = document.createElement("div");
  div.className = "bot-message";

  // 👇 ACÁ ESTÁ LA CLAVE
  if (response.type === "card") {
    div.innerHTML = response.content;
  } else {
    div.textContent = response.content;
  }

  chat.appendChild(div);
}
