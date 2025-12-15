// static/js/app.js
let ws = null;
const CHAT_ID = window.CHAT_ID || 1; // ? будет подставлено из шаблона

function connectWS() {
    if (ws) return; // уже подключены

    ws = new WebSocket(`ws://${location.host}/ws/chat/${CHAT_ID}`);

    ws.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        const div = document.createElement("div");
        div.className = msg.is_from_bot ? "bot" : "user";
        div.textContent = `${msg.is_from_bot ? "?" : "?"}: ${msg.message}`;
        document.getElementById("history").appendChild(div);
    };

    ws.onopen = () => {
        console.log("WS connected to chat", CHAT_ID);
    };

    ws.onclose = () => {
        ws = null;
        console.log("WS disconnected");
    };
}

async function sendMessage() {
    const userId = document.getElementById("userId").value;
    const message = document.getElementById("message").value;

    if (!message.trim()) return;

    const payload = {
        user_id: parseInt(userId),
        chat_id: CHAT_ID,  // ? берём из URL
        message: message.trim()
    };

    const resp = await fetch("/send_message", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
    });

    if (resp.ok) {
        document.getElementById("message").value = "";
        connectWS(); // подключаем WS, если ещё не подключены
    } else {
        alert("Ошибка отправки");
    }
}

async function loadMessages() {
    const resp = await fetch(`/chat/${CHAT_ID}/messages`);
    const data = await resp.json();

    const historyEl = document.getElementById("history");
    historyEl.innerHTML = "";
    data.messages.forEach(msg => {
        const div = document.createElement("div");
        div.className = msg.is_from_bot ? "bot" : "user";
        div.textContent = `${msg.is_from_bot ? "?" : "?"}: ${msg.message}`;
        historyEl.appendChild(div);
    });

    connectWS();
}

// Загружаем историю при старте
loadMessages();
window.sendMessage = sendMessage;
window.loadMessages = loadMessages;