const avatar = document.getElementById("avatar");
const avatarBox = document.getElementById("avatarBox");
const messages = document.getElementById("messages");
const input = document.getElementById("userInput");


/* Simula envío al backend */
async function sendMessage() {

  const text = input.value.trim();
  if (!text) return;

  addUserMessage(text);
  input.value = "";

  // Simular thinking
  await sleep(500);

  startSpeaking();

  // Simular respuesta
  await sleep(2500);

  const reply = "Esta es una respuesta de prueba del clon.";

  stopSpeaking();
  addBotMessage(reply);
}


/* Messages */

function addUserMessage(text) {
  const div = document.createElement("div");
  div.className = "msg-user";
  div.textContent = text;
  messages.appendChild(div);
  scrollDown();
}

function addBotMessage(text) {
  const div = document.createElement("div");
  div.className = "msg-bot";
  div.textContent = text;
  messages.appendChild(div);
  scrollDown();
}

function scrollDown() {
  messages.scrollTop = messages.scrollHeight;
}


/* Speaking Effects */

function startSpeaking() {
  avatar.classList.add("speaking");
  avatarBox.classList.add("speaking");
}

function stopSpeaking() {
  avatar.classList.remove("speaking");
  avatarBox.classList.remove("speaking");
}


/* Utils */

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}
