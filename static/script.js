const chat = document.getElementById("chat");
const form = document.getElementById("form");
const input = document.getElementById("input");

let typingDiv = null;

function addMessage(text, type){

  if(!text || text.trim() === ""){
    text = "…";
  }

  const div = document.createElement("div");
  div.className = `msg ${type}`;

  // Permite saltos de línea
  div.innerHTML = text.replace(/\n/g,"<br>");

  chat.appendChild(div);
  scrollBottom();
}

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

function hideTyping(){
  if(typingDiv){
    typingDiv.remove();
    typingDiv = null;
  }
}

function scrollBottom(){
  chat.scrollTop = chat.scrollHeight;
}

form.addEventListener("submit", async (e)=>{
  e.preventDefault();

  const text = input.value.trim();
  if(!text) return;

  addMessage(text,"user");
  input.value="";

  showTyping();

  try{

    const res = await fetch("/chat",{
      method:"POST",
      headers:{
        "Content-Type":"application/json"
      },
      body:JSON.stringify({ message: text })
    });

    const data = await res.json();

    hideTyping();

    addMessage(data.response || "Sin respuesta","bot");

  }catch(err){

    hideTyping();
    addMessage("Error de conexión","bot");

  }
});
