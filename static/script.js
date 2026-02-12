const chat = document.getElementById("chat");
const form = document.getElementById("form");
const input = document.getElementById("input");
const avatarBox = document.getElementById("avatarBox");

let typingDiv = null;

/* ===============================
   Avatar speaking
================================ */

function startSpeaking(){
  avatarBox.classList.add("speaking");
}

function stopSpeaking(){
  avatarBox.classList.remove("speaking");
}

/* ===============================
   Messages
================================ */

function addMessage(text, type){
  if(!text || text.trim()===""){
    text="…";
  }

  const div=document.createElement("div");
  div.className=`msg ${type}`;
  div.innerHTML=text.replace(/\n/g,"<br>");
  chat.appendChild(div);
  scrollBottom();
}

/* ===============================
   Typing
================================ */

function showTyping(){
  typingDiv=document.createElement("div");
  typingDiv.className="msg bot typing";
  typingDiv.innerHTML="<span>.</span><span>.</span><span>.</span>";
  chat.appendChild(typingDiv);
  scrollBottom();
  startSpeaking();
}

function hideTyping(){
  if(typingDiv){
    typingDiv.remove();
    typingDiv=null;
  }
  stopSpeaking();
}

/* ===============================
   Scroll
================================ */

function scrollBottom(){
  chat.scrollTop=chat.scrollHeight;
}

/* ===============================
   Submit
================================ */

form.addEventListener("submit",async(e)=>{
  e.preventDefault();

  const text=input.value.trim();
  if(!text) return;

  addMessage(text,"user");
  input.value="";
  input.disabled=true;

  showTyping();

  try{
    const res=await fetch("/chat",{
      method:"POST",
      headers:{ "Content-Type":"application/json" },
      body:JSON.stringify({ message:text })
    });

    const data=await res.json();

    hideTyping();
    addMessage(data.content || "Sin respuesta","bot");
  }
  catch(err){
    console.error(err);
    hideTyping();
    addMessage("Error de conexión","bot");
  }
  finally{
    input.disabled=false;
    input.focus();
  }
});

/* ===== Optional actions ===== */

document.getElementById("clearChat").onclick=()=>{
  chat.innerHTML="";
};
