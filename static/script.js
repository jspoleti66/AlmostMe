const chat = document.getElementById("chat");
const form = document.getElementById("form");
const input = document.getElementById("input");
const avatar = document.getElementById("chatAvatar");
const video = document.getElementById("avatarVideo");

/* ===== CONFIG ===== */
const WORDS_PER_SECOND = 2.7;

/* ===== VIDEO CONTROL ===== */

function playVideo(){
  video.currentTime = 0;
  video.play();
}

function stopVideo(){
  video.pause();
  video.currentTime = 0;
}

/* ===== AVATAR STATES ===== */

function startThinking(){
  avatar.classList.add("floating","thinking");
  avatar.classList.remove("speaking");
}

function startSpeaking(){
  avatar.classList.remove("thinking");
  avatar.classList.add("speaking");
  playVideo();
}

function stopAvatar(){
  avatar.classList.remove("floating","thinking","speaking");
  stopVideo();
}

/* ===== CHAT ===== */

function addMessage(text,type){
  const div=document.createElement("div");
  div.className=`msg ${type}`;
  div.innerHTML=(text || "…").replace(/\n/g,"<br>");
  chat.appendChild(div);
  chat.scrollTop=chat.scrollHeight;
}

/* ===== DURACIÓN REALISTA ===== */

function calculateSpeechDuration(text){
  const words = text.trim().split(/\s+/).length;
  const seconds = words / WORDS_PER_SECOND;
  return seconds * 1000;
}

/* ===== FORM ===== */

form.addEventListener("submit",async(e)=>{
  e.preventDefault();

  const text=input.value.trim();
  if(!text) return;

  addMessage(text,"user");
  input.value="";

  startThinking();

  try{
    const res=await fetch("/chat",{
      method:"POST",
      headers:{ "Content-Type":"application/json" },
      body:JSON.stringify({ message:text })
    });

    if(!res.ok) throw new Error("HTTP error");

    const data=await res.json();
    const reply = data.content || data.response || "Sin respuesta";

    addMessage(reply,"bot");

    startSpeaking();

    const duration = calculateSpeechDuration(reply);

    setTimeout(() => {
      stopAvatar();
    }, duration);

  }catch(err){
    console.error(err);
    stopAvatar();
    addMessage("No pude conectar con el servidor","bot");
  }
});
