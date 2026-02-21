const chat = document.getElementById("chat");
const form = document.getElementById("form");
const input = document.getElementById("input");
const avatar = document.getElementById("chatAvatar");
const video = document.getElementById("avatarVideo");

/* ===== VIDEO CONTROL ===== */
function playVideo() {
  if (video.paused) {
    video.currentTime = 0;
    video.play().catch(e => console.warn("Video play blocked:", e));
  }
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

/* ===== CHAT HELPERS ===== */
function addMessageContainer(type) {
  const div = document.createElement("div");
  div.className = `msg ${type}`;
  chat.appendChild(div);
  return div;
}

/* ===== FORM SUBMIT (STREAMING) ===== */
form.addEventListener("submit", async (e) => {
  e.preventDefault();

  const text = input.value.trim();
  if (!text) return;

  // Mensaje del usuario
  const userDiv = addMessageContainer("user");
  userDiv.innerText = text;
  input.value = "";
  chat.scrollTop = chat.scrollHeight;

  startThinking();

  try {
    const res = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text })
    });

    if (!res.ok) throw new Error("HTTP error");

    const contentType = res.headers.get('content-type');

    // CASO A: Respuesta JSON (Manuales/VCards o Errores)
    if (contentType && contentType.includes('application/json')) {
      const data = await res.json();
      stopAvatar(); // Opcional: podrías ponerlo a hablar brevemente
      const botDiv = addMessageContainer("bot");
      botDiv.innerHTML = data.content;
    } 
    
    // CASO B: Streaming de texto (Conversación normal)
    else {
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      const botDiv = addMessageContainer("bot");
      
      startSpeaking();

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        // Reemplazamos saltos de línea por <br> para el formato
        botDiv.innerHTML += chunk.replace(/\n/g, "<br>");
        chat.scrollTop = chat.scrollHeight;
      }
      
      // Una vez que el stream termina, esperamos un microsegundo y paramos el avatar
      setTimeout(stopAvatar, 500);
    }

  } catch (err) {
    console.error(err);
    stopAvatar();
    const errorDiv = addMessageContainer("bot");
    errorDiv.innerText = "No pude conectar con el servidor.";
  }
});
