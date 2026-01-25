const chat = document.getElementById("chat");
const form = document.getElementById("form");
const input = document.getElementById("input");

function addMessage(text, type){
  const div = document.createElement("div");
  div.className = `msg ${type}`;
  div.textContent = text;
  chat.appendChild(div);
  chat.scrollTop = chat.scrollHeight;
}

form.addEventListener("submit", async (e)=>{
  e.preventDefault();

  const text = input.value.trim();
  if(!text) return;

  addMessage(text,"user");
  input.value="";

  try{
    const res = await fetch("/chat",{
      method:"POST",
      headers:{
        "Content-Type":"application/json"
      },
      body:JSON.stringify({message:text})
    });

    const data = await res.json();
    addMessage(data.response,"bot");

  }catch(err){
    addMessage("Error de conexión","bot");
  }
});
