const chat = document.getElementById("chat");
const form = document.getElementById("form");
const input = document.getElementById("input");
const avatar = document.getElementById("chatAvatar");
const video = document.getElementById("avatarVideo");

/* ===== CONFIG ===== */
const WORDS_PER_SECOND = 2.7;
const TYPING_SPEED = 1000 / WORDS_PER_SECOND; // ms por palabra
const SPEECH_LEAD_TIME = 300;

/* ===== VIDEO CONTROL ===== */

function playVideo() {
  video.currentTime = 0;
  video.play();
}

function stopVideo() {
  video.pause();
  video.currentTime = 0;
}

/* ===== AVATAR STATES ===== */

function startThinking() {
  avatar.classList.add("floating", "thinking");
  avatar.classList.remove("speaking");
}

function startSpeaking() {
  avatar.classList.remove("thinking");
  avatar.classList.add("speaking");
  playVideo();
}

function stopAvatar() {
  avatar.classList.remove("floating", "thinking", "speaking");
  stopVideo();
}

/* ===== CHAT ===== */

function addMessage(text, type) {
  const div = document.createElement("div");
  div.className = `msg ${type}`;
  div.innerHTML = (text || "…").replace(/\n/g, "<br>");
  chat.appendChild(div);
  chat.scrollTop = chat.scrollHeight;
  return div;
}

/* ===== TYPING EFFECT ===== */

function typeMessage(element, fullText) {
  return new Promise((resolve) => {
    const words = fullText.split(" ");
    let index = 0;

    function addWord() {
      if (index < words.length) {
        element.innerHTML += (index === 0 ? "" : " ") + words[index];
        chat.scrollTop = chat.scrollHeight;
        index++;
        setTimeout(addWord, TYPING_SPEED);
      } else {
        resolve();
      }
    }

    addWord();
  });
}

/* ===== FORM ===== */

form.addEventListener("submit", async (e) => {
  e.preventDefault();

  const text = input.value.trim();
  if (!text) return;

  addMessage(text, "user");
  input.value = "";

  startThinking();

  try {
    const res = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text })
    });

    if (!res.ok) throw new Error("HTTP error");

    const data = await res.json();
    const reply = data.content || data.response || "Sin respuesta";

    // 🔹 Mostrar "..." mientras piensa
    const typingBubble = addMessage("...", "bot");

    // 🔹 Pequeño delay natural antes de empezar a hablar
    setTimeout(async () => {

      startSpeaking();

      // Limpiar los ...
      typingBubble.innerHTML = "";

      // Escribir palabra por palabra
      await typeMessage(typingBubble, reply);

      // Cuando termina de escribir, detener avatar
      stopAvatar();

    }, SPEECH_LEAD_TIME);

  } catch (err) {
    console.error(err);
    stopAvatar();
    addMessage("No pude conectar con el servidor", "bot");
  }
});
