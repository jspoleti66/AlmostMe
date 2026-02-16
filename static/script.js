const chat = document.getElementById("chat");
const form = document.getElementById("form");
const input = document.getElementById("input");
const avatar = document.getElementById("chatAvatar");
const video = document.getElementById("avatarVideo");

/* ===== CONFIG ===== */
const WORDS_PER_SECOND = 2.6;
const BASE_DELAY = 1000 / WORDS_PER_SECOND;
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
  avatar.classList.remove("speaking", "idle");
}

function startSpeaking() {
  avatar.classList.remove("thinking");
  avatar.classList.add("speaking");
  playVideo();
}

function setIdle() {
  avatar.classList.remove("thinking", "speaking");
  avatar.classList.add("idle");
  stopVideo();
}

/* ===== CHAT ===== */

function addMessage(text, type) {
  const div = document.createElement("div");
  div.className = `msg ${type}`;
  div.innerHTML = text || "";
  chat.appendChild(div);
  chat.scrollTop = chat.scrollHeight;
  return div;
}

/* ===== TYPING EFFECT ===== */

function typeMessage(element, fullText) {
  return new Promise((resolve) => {
    const words = fullText.split(" ");
    let index = 0;

    element.innerHTML = `<span class="cursor">|</span>`;

    function addWord() {
      if (index < words.length) {

        let delay = BASE_DELAY;

        // Micro pausas naturales
        if (/[.,!?]$/.test(words[index])) delay *= 2;
        if (/[,;:]$/.test(words[index])) delay *= 1.5;

        element.innerHTML =
          words.slice(0, index + 1).join(" ") +
          ` <span class="cursor">|</span>`;

        chat.scrollTop = chat.scrollHeight;
        index++;
        setTimeout(addWord, delay);

      } else {
        element.innerHTML = fullText.replace(/\n/g, "<br>");
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

    const typingBubble = addMessage("...", "bot");

    setTimeout(async () => {

      startSpeaking();

      await typeMessage(typingBubble, reply);

      setIdle();

    }, SPEECH_LEAD_TIME);

  } catch (err) {
    console.error(err);
    setIdle();
    addMessage("No pude conectar con el servidor", "bot");
  }
});

/* ===== INIT ===== */
setIdle();
