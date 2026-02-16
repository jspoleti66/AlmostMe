const chat = document.getElementById("chat");
const form = document.getElementById("form");
const input = document.getElementById("input");
const avatar = document.getElementById("chatAvatar");
const video = document.getElementById("avatarVideo");

/* ===== CONFIG ===== */
const MIN_SPEAK_TIME = 1200; // tiempo mínimo que el avatar habla aunque la respuesta sea instantánea
const THINKING_DELAY = 300;  // pequeño delay antes de mostrar texto

/* ===== VIDEO CONTROL ===== */

function playVideo() {
  video.currentTime = 0;
  video.play().catch(() => {});
}

function stopVideo() {
  video.pause();
  video.currentTime = 0;
}

/* ===== AVATAR STATES ===== */

function startSpeaking() {
  avatar.classList.add("speaking");
  avatar.classList.remove("thinking");
  playVideo();
}

function stopSpeaking() {
  avatar.classList.remove("speaking");
  stopVideo();
}

/* ===== CHAT ===== */

function addMessage(text, type) {
  const div = document.createElement("div");
  div.className = `msg ${type}`;
  div.innerHTML = text.replace(/\n/g, "<br>");
  chat.appendChild(div);
  chat.scrollTop = chat.scrollHeight;
  return div;
}

/* ===== FORM ===== */

form.addEventListener("submit", async (e) => {
  e.preventDefault();

  const text = input.value.trim();
  if (!text) return;

  addMessage(text, "user");
  input.value = "";

  // 🔥 ANTICIPACIÓN INTELIGENTE
  startSpeaking();

  const speakStartTime = Date.now();

  try {
    const fetchPromise = fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text })
    });

    // 🔹 No esperamos inmediatamente
    const res = await fetchPromise;

    if (!res.ok) throw new Error("HTTP error");

    const data = await res.json();
    const reply = data.content || data.response || "Sin respuesta";

    // 🔹 Garantizar que el avatar no corte demasiado rápido
    const elapsed = Date.now() - speakStartTime;
    const remaining = Math.max(0, MIN_SPEAK_TIME - elapsed);

    setTimeout(() => {
      addMessage(reply, "bot");
      stopSpeaking();
    }, remaining + THINKING_DELAY);

  } catch (err) {
    console.error(err);
    addMessage("No pude conectar con el servidor", "bot");
    stopSpeaking();
  }
});
