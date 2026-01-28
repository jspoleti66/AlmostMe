const chat = document.getElementById("chat");
const form = document.getElementById("form");
const input = document.getElementById("input");

// Avatar
const avatar = document.getElementById("avatar");

let typingDiv = null;


/* ===============================
   Activar / desactivar speaking
================================ */

function startSpeaking(){
  if(avatar){
    avatar.classList.add("avatar-speaking");
  }
}

function stopSpeaking(){
  if(avatar){
    avatar.classList.remove("avatar-speaking");
  }
}


/* ===============================
   Agregar mensaje
================================ */

function addMessage(text, type){

  if(!text || text.trim() === ""){
    text = "…";
  }

  const div = document.createElement("div");
  div.className = `msg ${type}`;

  div.innerHTML = text.replace(/\n/g, "<br>");

  chat.appendChild(div);
  scrollBottom();
}


/* ===============================
   Mostrar "escribiendo"
================================ */

function showTyping(){

  typingDiv = document.createElement("div");
  typingDiv.className = "msg bot typing";

  typingDiv.innerHTML = `
    <span>.</span>
    <span>.</span>
    <span>.</span>
  `;

  chat.appendChild(typingDiv);
  scrollBottom();

  // Activa avatar
  startSpeaking();
}


/* ===============================
   Ocultar "escribiendo"
================================ */

function hideTyping(){

  if(typingDiv){
    typingDiv.remove();
    typingDiv = null;
  }

  // Desactiva avatar
  stopSpeaking();
}


/* ===============================
   Scroll
================================ */

function scrollBottom(){
  chat.scrollTop = chat.scrollHeight;
}


/* ===============================
   Envío
================================ */

form.addEventListener("submit", async (e)=>{

  e.preventDefault();

  const text = input.value.trim();

  if(!text) return;

  // Usuario
  addMessage(text, "user");

  input.value = "";

  showTyping();

  try{

    const res = await fetch("/chat",{
      method: "POST",
      headers:{
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        message: text
      })
    });

    const data = await res.json();

    hideTyping();

    // Bot
    addMessage(data.content || "Sin respuesta", "bot");

  }
  catch(err){

    console.error("Error:", err);

    hideTyping();

    addMessage("Error de conexión con el servidor", "bot");
  }

});
