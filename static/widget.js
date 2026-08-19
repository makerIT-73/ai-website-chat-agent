(function () {
  const BUSINESS_NAME = "__BUSINESS_NAME__";
  const GREETING = "__GREETING__";
  const COLOR = "__WIDGET_COLOR__";
  const POSITION = "__WIDGET_POSITION__"; // right / left
  const API_URL = (document.currentScript && document.currentScript.src
    ? document.currentScript.src.replace("/widget.js", "")
    : "") + "/api/chat";

  const side = POSITION === "left" ? "left" : "right";

  const style = document.createElement("style");
  style.textContent = `
    .aiw-bubble {
      position: fixed; bottom: 24px; ${side}: 24px; z-index: 999999;
      width: 60px; height: 60px; border-radius: 50%;
      background: ${COLOR}; color: white; border: none; cursor: pointer;
      box-shadow: 0 4px 16px rgba(0,0,0,.2);
      display: flex; align-items: center; justify-content: center;
      font-size: 26px; transition: transform .15s ease;
    }
    .aiw-bubble:hover { transform: scale(1.06); }
    .aiw-panel {
      position: fixed; bottom: 96px; ${side}: 24px; z-index: 999999;
      width: 340px; max-height: 480px; background: #fff;
      border-radius: 16px; box-shadow: 0 8px 30px rgba(0,0,0,.18);
      display: none; flex-direction: column; overflow: hidden;
      font-family: -apple-system, Segoe UI, Roboto, sans-serif;
    }
    .aiw-panel.open { display: flex; }
    .aiw-header {
      background: ${COLOR}; color: white; padding: 14px 16px;
      font-weight: 600; font-size: 15px;
    }
    .aiw-messages {
      flex: 1; overflow-y: auto; padding: 12px; background: #F7F8FA;
      display: flex; flex-direction: column; gap: 8px;
    }
    .aiw-msg { max-width: 80%; padding: 8px 12px; border-radius: 12px; font-size: 14px; line-height: 1.4; }
    .aiw-msg.bot { align-self: flex-start; background: #fff; border: 1px solid #E5E7EB; }
    .aiw-msg.user { align-self: flex-end; background: ${COLOR}; color: white; }
    .aiw-inputbar { display: flex; border-top: 1px solid #E5E7EB; }
    .aiw-inputbar input {
      flex: 1; border: none; padding: 12px; font-size: 14px; outline: none;
    }
    .aiw-inputbar button {
      border: none; background: none; color: ${COLOR}; font-weight: 600;
      padding: 0 14px; cursor: pointer;
    }
    .aiw-typing { font-size: 13px; color: #888; padding: 4px 12px; }
  `;
  document.head.appendChild(style);

  const bubble = document.createElement("button");
  bubble.className = "aiw-bubble";
  bubble.innerHTML = "💬";
  document.body.appendChild(bubble);

  const panel = document.createElement("div");
  panel.className = "aiw-panel";
  panel.innerHTML = `
    <div class="aiw-header">${BUSINESS_NAME}</div>
    <div class="aiw-messages" id="aiw-messages"></div>
    <div class="aiw-typing" id="aiw-typing" style="display:none;">печатает…</div>
    <div class="aiw-inputbar">
      <input id="aiw-input" type="text" placeholder="Напишите сообщение..." />
      <button id="aiw-send">➤</button>
    </div>
  `;
  document.body.appendChild(panel);

  const messagesEl = panel.querySelector("#aiw-messages");
  const inputEl = panel.querySelector("#aiw-input");
  const typingEl = panel.querySelector("#aiw-typing");
  let history = [];

  function addMessage(role, text) {
    const div = document.createElement("div");
    div.className = "aiw-msg " + (role === "user" ? "user" : "bot");
    div.textContent = text;
    messagesEl.appendChild(div);
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  function openPanel() {
    panel.classList.add("open");
    if (history.length === 0) {
      addMessage("assistant", GREETING);
      history.push({ role: "assistant", content: GREETING });
    }
    inputEl.focus();
  }

  bubble.addEventListener("click", () => {
    panel.classList.contains("open") ? panel.classList.remove("open") : openPanel();
  });

  async function send() {
    const text = inputEl.value.trim();
    if (!text) return;
    inputEl.value = "";
    addMessage("user", text);
    history.push({ role: "user", content: text });
    typingEl.style.display = "block";

    try {
      const res = await fetch(API_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ history }),
      });
      const data = await res.json();
      typingEl.style.display = "none";
      if (!res.ok) throw new Error(data.detail || "Ошибка сервера");
      addMessage("assistant", data.reply);
      history.push({ role: "assistant", content: data.reply });
    } catch (e) {
      typingEl.style.display = "none";
      addMessage("assistant", "Извините, произошла ошибка. Попробуйте позже.");
    }
  }

  panel.querySelector("#aiw-send").addEventListener("click", send);
  inputEl.addEventListener("keydown", (e) => {
    if (e.key === "Enter") send();
  });
})();
