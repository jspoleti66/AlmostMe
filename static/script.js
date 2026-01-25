const chat = document.getElementById("chat");
const form = document.getElementById("form");
const input = document.getElementById("input");

let typingDiv = null;

/* ===============================
   Agregar mensaje al chat
================================ */

function addMessage(text, type){

  if(!text || text.trim() === ""){
    text = "…";
  }

  const div = document.createElement("div");
  div.className = `msg ${type}`;

  // Soporta saltos de línea
  div.innerHTML = text.replace(/\n/g, "<br>");

  chat.appendChild(div);
  scrollBottom();
}

/* ===============================
   Mostrar "escribiendo..."
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
}

/* ===============================
   Ocultar "escribiendo..."
================================ */

function hideTyping(){

  if(typingDiv){
    typingDiv.remove();
    typingDiv = null;
  }
}

/* ===============================
   Scroll automático
================================ */

function scrollBottom(){
  chat.scrollTop = chat.scrollHeight;
}

/* ===============================
   Envío del formulario
================================ */

form.addEventListener("submit", async (e)=>{

  e.preventDefault();

  const text = input.value.trim();

  if(!text) return;

  // Mensaje del usuario
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

    // 🔑 IMPORTANTE: leer "content"
    addMessage(data.content || "Sin respuesta", "bot");

  }
  catch(err){

    console.error("Error:", err);

    hideTyping();

    addMessage("Error de conexión con el servidor", "bot");
  }

});
