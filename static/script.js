const chat = document.getElementById("chat");
const form = document.getElementById("form");
const input = document.getElementById("input");
const avatar = document.getElementById("chatAvatar");
const video = document.getElementById("avatarVideo");

function addMessage(text, sender){
  const msg = document.createElement("div");
  msg.classList.add("msg", sender);
  msg.innerText = text;
  chat.appendChild(msg);
  chat.scrollTop = chat.scrollHeight;
}

function speak(text){

  avatar.classList.add("speaking");

  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = "es-AR";

  utterance.onstart = () => {
    video.currentTime = 0;
    video.play();
  };

  utterance.onend = () => {
    video.pause();
    avatar.classList.remove("speaking");
  };

  speechSynthesis.speak(utterance);
}

form.addEventListener("submit", (e)=>{
  e.preventDefault();

  const text = input.value.trim();
  if(!text) return;

  addMessage(text,"user");
  input.value = "";

  setTimeout(()=>{
    const reply = "Dijiste: " + text;
    addMessage(reply,"bot");
    speak(reply);
  }, 400);
});
