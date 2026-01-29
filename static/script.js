const avatarBox = document.getElementById("avatarBox");

/* ACTIVAR EFECTO */
function startSpeaking() {
  avatarBox.classList.add("speaking");
}

/* DESACTIVAR EFECTO */
function stopSpeaking() {
  avatarBox.classList.remove("speaking");
}


/* ===== DEMO (BORRAR EN PRODUCCIÓN) ===== */
/* Simula habla cada 5s */

setInterval(() => {

  startSpeaking();

  setTimeout(() => {
    stopSpeaking();
  }, 1800);

}, 5000);
