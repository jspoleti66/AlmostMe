const chat = document.getElementById("chat");
const form = document.getElementById("form");
const input = document.getElementById("input");
const avatarBox = document.getElementById("avatarBox");

function addMessage(text, sender){
  const msg = document.createElement("div");
  msg.className = `message ${sender}`;
  msg.textContent = text;
  chat.appendChild(msg);
  chat.scrollTop = chat.scrollHeight;
}

/* ===== AVATAR STATES ===== */

function startThinking(){
  avatarBox.classList.remove("speaking");
  avatarBox.classList.add("thinking");
}

function stopThinking(){
  avatarBox.classList.remove("thinking");
}

function startSpeaking(){
  avatarBox.classList.remove("thinking");
  avatarBox.classList.add("speaking");
}

function stopSpeaking(){
  avatarBox.classList.remove("speaking");
}

/* ===== FORM ===== */

form.addEventListener("submit", async (e)=>{
  e.preventDefault();

  const text = input.value.trim();
  if(!text) return;

  addMessage(text,"user");
  input.value="";

  startThinking();

  try{
    const res = await fetch("/chat",{
      method:"POST",
      headers:{ "Content-Type":"application/json" },
      body:JSON.stringify({ message:text })
    });

    const data = await res.json();

    stopThinking();
    startSpeaking();

    addMessage(data.response,"bot");

    // simulamos tiempo de habla
    setTimeout(()=>{
      stopSpeaking();
    }, Math.min(3000, data.response.length * 30));

  }catch(err){
    stopThinking();
    addMessage("Error de conexión","bot");
  }
});
