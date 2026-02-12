const chat = document.getElementById("chat");
const form = document.getElementById("form");
const input = document.getElementById("input");
const avatar = document.getElementById("floatingAvatar");

/* ===== AVATAR STATES ===== */

function setThinking(){
  avatar.classList.remove("speaking");
  avatar.classList.add("thinking");
}

function setSpeaking(){
  avatar.classList.remove("thinking");
  avatar.classList.add("speaking");
}

function clearAvatar(){
  avatar.classList.remove("thinking","speaking");
}

/* ===== CHAT ===== */

function addMessage(text,type){
  const div=document.createElement("div");
  div.className=`msg ${type}`;
  div.innerHTML=text.replace(/\n/g,"<br>");
  chat.appendChild(div);
  chat.scrollTop=chat.scrollHeight;
}

/* ===== FORM ===== */

form.addEventListener("submit",async(e)=>{
  e.preventDefault();

  const text=input.value.trim();
  if(!text) return;

  addMessage(text,"user");
  input.value="";

  setThinking();

  try{
    const res=await fetch("/chat",{
      method:"POST",
      headers:{ "Content-Type":"application/json" },
      body:JSON.stringify({ message:text })
    });

    if(!res.ok) throw new Error("HTTP error");

    const data=await res.json();

    const reply = data.content || data.response || "Sin respuesta";

    setSpeaking();
    addMessage(reply,"bot");

    setTimeout(clearAvatar, Math.min(2500, reply.length * 25));

  }catch(err){
    console.error(err);
    clearAvatar();
    addMessage("No pude conectar con el servidor","bot");
  }
});
