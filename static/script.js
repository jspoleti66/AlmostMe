<script>
  const chat = document.getElementById("chat");
  const input = document.getElementById("input");
  const send = document.getElementById("send");

  function addMessage(text, type) {
    const div = document.createElement("div");
    div.className = "msg " + type;
    div.textContent = text;
    chat.appendChild(div);
    chat.scrollTop = chat.scrollHeight;
  }

  async function sendMessage() {
    const text = input.value.trim();
    if (!text) return;

    addMessage(text, "user");
    input.value = "";

    // indicador "pensando"
    const thinking = document.createElement("div");
    thinking.className = "msg bot";
    thinking.textContent = "Pensando…";
    chat.appendChild(thinking);
    chat.scrollTop = chat.scrollHeight;

    try {
      const res = await fetch("/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ message: text })
      });

      const data = await res.json();
      thinking.remove();
      addMessage(data.reply || "Sin respuesta", "bot");

    } catch (err) {
      thinking.remove();
      addMessage("Error al conectar con el servidor", "bot");
      console.error(err);
    }
  }

  send.onclick = sendMessage;

  input.addEventListener("keypress", e => {
    if (e.key === "Enter") sendMessage();
  });
</script>
