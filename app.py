"""
Backend AI-чат-агента для сайта бизнеса.

Что делает:
- отдаёт статический /static/widget.js, который клиент вставляет на сайт
- принимает сообщения на /api/chat, собирает системный промпт из config.py
  и пересылает в LLM (Anthropic или OpenAI — выбор в config.py)
- ключ API читается из .env и никогда не попадает в браузер клиента

Запуск локально:  uvicorn app:app --reload --port 8000
"""

import os
import time
from collections import defaultdict, deque
from typing import List, Literal

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import config

load_dotenv()

app = FastAPI(title=f"AI-агент — {config.BUSINESS_NAME}")
app.mount("/static", StaticFiles(directory="static"), name="static")

# --- CORS: разрешаем обращаться к API только с домена клиента ---
allowed_origins = [config.ALLOWED_ORIGIN] if config.ALLOWED_ORIGIN != "*" else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)

API_KEY = os.getenv("API_KEY")

# --- простой лимитер запросов по IP (в памяти, для одного процесса/VPS) ---
_request_log: dict[str, deque] = defaultdict(deque)


def check_rate_limit(ip: str):
    now = time.time()
    window = 60  # секунд
    log = _request_log[ip]
    while log and now - log[0] > window:
        log.popleft()
    if len(log) >= config.RATE_LIMIT_PER_MINUTE:
        raise HTTPException(429, "Слишком много сообщений. Подождите немного и попробуйте снова.")
    log.append(now)


# ---------- системный промпт, собранный из конфига ----------
def build_system_prompt() -> str:
    services_txt = "\n".join(
        f"- {s['name']}: {s['price']}. {s['desc']}" for s in config.SERVICES
    )
    faq_txt = "\n".join(f"Q: {f['q']}\nA: {f['a']}" for f in config.FAQ)

    return f"""Ты — чат-агент на сайте бизнеса "{config.BUSINESS_NAME}".
Тон общения: {config.TONE}

Список услуг и цен:
{services_txt}

Частые вопросы и ответы (используй как источник фактов):
{faq_txt}

Контакты для передачи человеку, если чат-бот не справляется:
Телефон: {config.CONTACT['phone']}
Telegram: {config.CONTACT['telegram']}

Правила:
{config.RULES}

Формат ответа:
- Пиши обычным текстом, без markdown-разметки (без **, без #, без списков через "-").
- Если нужно перечислить несколько пунктов — пиши их в одном абзаце через запятую или с новой строки, без звёздочек и тире.
"""


# ---------- модели запроса/ответа ----------
class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    history: List[Message]  # вся история диалога, backend не хранит состояние


class ChatResponse(BaseModel):
    reply: str


# ---------- вызов LLM ----------
def call_anthropic(system_prompt: str, history: List[Message]) -> str:
    import anthropic

    client = anthropic.Anthropic(api_key=API_KEY)
    resp = client.messages.create(
        model=config.MODEL,
        max_tokens=500,
        system=system_prompt,
        messages=[{"role": m.role, "content": m.content} for m in history],
    )
    return "".join(block.text for block in resp.content if block.type == "text")


def call_openai(system_prompt: str, history: List[Message]) -> str:
    from openai import OpenAI

    client = OpenAI(api_key=API_KEY)
    resp = client.chat.completions.create(
        model=config.MODEL,
        max_tokens=500,
        messages=[{"role": "system", "content": system_prompt}]
        + [{"role": m.role, "content": m.content} for m in history],
    )
    return resp.choices[0].message.content


@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest, request: Request):
    client_ip = request.client.host if request.client else "unknown"
    check_rate_limit(client_ip)

    if not API_KEY:
        raise HTTPException(
            500,
            "API_KEY не задан. Добавьте его в файл .env (см. .env.example).",
        )
    if not req.history:
        raise HTTPException(400, "Пустая история сообщений")

    system_prompt = build_system_prompt()
    try:
        if config.LLM_PROVIDER == "anthropic":
            reply = call_anthropic(system_prompt, req.history)
        elif config.LLM_PROVIDER == "openai":
            reply = call_openai(system_prompt, req.history)
        else:
            raise HTTPException(500, f"Неизвестный LLM_PROVIDER: {config.LLM_PROVIDER}")
    except Exception as e:
        raise HTTPException(502, f"Ошибка обращения к LLM: {e}")

    return ChatResponse(reply=reply)


# ---------- отдаём настроенный под клиента widget.js ----------
@app.get("/widget.js")
def widget_js():
    with open("static/widget.js", "r", encoding="utf-8") as f:
        js = f.read()
    # подставляем настройки бизнеса прямо в скрипт
    js = js.replace("__BUSINESS_NAME__", config.BUSINESS_NAME)
    js = js.replace("__GREETING__", config.GREETING)
    js = js.replace("__WIDGET_COLOR__", config.WIDGET_COLOR)
    js = js.replace("__WIDGET_POSITION__", config.WIDGET_POSITION)
    return PlainTextResponse(js, media_type="application/javascript")


@app.get("/demo")
def demo_page():
    return FileResponse("static/demo.html")


@app.get("/health")
def health():
    return {"status": "ok", "business": config.BUSINESS_NAME}
