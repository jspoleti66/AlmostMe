const messages = document.getElementById("messages");
const input = document.getElementById("user-input");
const button = document.getElementById("send-button");
const avatarVideo = document.getElementById("avatar-video");

// CONFIGURA TU VIDEO AQUÍ
avatarVideo.src = "/static/avatar.mp4";

let speakingInterval = null;

/* ========================
   CHAT UI
======================== */

function addUserMessage(text) {
    const div = document.createElement("div");
    div.className = "user-message";
    div.innerText = text;
    messages.appendChild(div);
    messages.scrollTop = messages.scrollHeight;
}

function addBotMessage(text) {
    const div = document.createElement("div");
    div.className = "bot-message";
    div.innerText = text;
    messages.appendChild(div);
    messages.scrollTop = messages.scrollHeight;
}

/* ========================
   DURACIÓN ESTIMADA
======================== */

function estimateSpeechDuration(text) {
    const words = text.trim().split(/\s+/).length;
    return words / 2.5; // 2.5 palabras por segundo
}

/* ========================
   VIDEO ADAPTATIVO
======================== */

function speakWithVideo(text) {

    const durationNeeded = estimateSpeechDuration(text);

    avatarVideo.loop = false;
    avatarVideo.playbackRate = 0.95 + Math.random() * 0.1;
    avatarVideo.currentTime = 0;

    avatarVideo.play();

    let elapsed = 0;
    const videoDuration = 5; // duración real de tu video

    if (speakingInterval) clearInterval(speakingInterval);

    speakingInterval = setInterval(() => {

        elapsed += videoDuration;

        if (elapsed >= durationNeeded) {
            clearInterval(speakingInterval);
            avatarVideo.pause();
            avatarVideo.currentTime = 0;
        } else {
            avatarVideo.currentTime = 0;
            avatarVideo.play();
        }

    }, videoDuration * 1000);
}

/* ========================
   BACKEND CALL
======================== */

async function sendMessage() {

    const text = input.value.trim();
    if (!text) return;

    addUserMessage(text);
    input.value = "";

    const response = await fetch("/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text })
    });

    const data = await response.json();
    const reply = data.reply;

    addBotMessage(reply);
    speakWithVideo(reply);
}

button.addEventListener("click", sendMessage);

input.addEventListener("keypress", function(e) {
    if (e.key === "Enter") {
        sendMessage();
    }
});
