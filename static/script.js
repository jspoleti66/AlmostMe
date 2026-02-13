const chat = document.getElementById("chat");
const input = document.getElementById("messageInput");
const button = document.getElementById("sendBtn");
const avatar = document.getElementById("avatar");
const video = document.getElementById("avatarVideo");

function addMessage(text, sender){
  const msg = document.createElement("div");
  msg.classList.add("msg", sender);
  msg.innerText = text;
  chat.appendChild(msg);

  chat.scrollTop = chat.scrollHeight;
}

function simulateSpeaking(text){

  const duration = Math.max(text.length * 40, 1200);

  avatar.classList.add("speaking","floating");

  video.currentTime = 0;
  video.play();

  setTimeout(()=>{
    video.pause();
    avatar.classList.remove("speaking","floating");
  }, duration);
}

button.addEventListener("click", sendMessage);
input.addEventListener("keypress", e=>{
  if(e.key==="Enter") sendMessage();
});

function sendMessage(){
  const text = input.value.trim();
  if(!text) return;

  addMessage(text,"user");
  input.value="";

  setTimeout(()=>{
    const reply = "Estoy bien, gracias.";
    addMessage(reply,"bot");
    simulateSpeaking(reply);
  }, 500);
}
