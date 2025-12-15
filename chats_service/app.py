import json
import logging
from fastapi import FastAPI, HTTPException, Depends
from utils.config import KAFKA_BROKER
from kafka import KafkaProducer
from pydantic import BaseModel
from db_scripts.chats_tables import DataBaseChats
from fastapi.websockets import WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi import Cookie, Depends, HTTPException, Request, status
from jose import JWTError, jwt
from utils.config import SECRET_KEY, ALGORITHM

db = DataBaseChats()  # ← один раз для всего приложения
service_message_alive = False
producer = KafkaProducer(
    bootstrap_servers=[KAFKA_BROKER],
    api_version=(4,1,0),
    key_serializer=lambda k: str(k).encode('utf-8'),
    value_serializer=lambda m: json.dumps(m).encode('utf-8'))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

app = FastAPI(title="Chats Service")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

def get_auth_data():
    return {"secret_key": SECRET_KEY, "algorithm": ALGORITHM}

def get_token(request: Request):
    token = request.cookies.get('users_access_token')
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Token not found')
    return token


async def get_current_user_from_cookie(token: str = Depends(get_token)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=401, detail='Invalid token')

    username = payload.get("sub")
    if not username:
        raise HTTPException(status_code=401, detail='Missing username')

    return username


    return {"status": "ok", "detail": "Bot message broadcasted"}
@app.get("/chat/{chat_id}")
async def chat_page(
    request: Request,
    chat_id: int,
    username: str = Depends(get_current_user_from_cookie)
):

    return templates.TemplateResponse("index.html", {
        "request": request,
        "chat_id": chat_id,
        "username": username
    })

connections: dict[int, list[WebSocket]] = {}
@app.websocket("/ws/chat/{chat_id}")
async def websocket_chat(websocket: WebSocket, chat_id: int):
    await websocket.accept()

    if chat_id not in connections:
        connections[chat_id] = []

    connections[chat_id].append(websocket)

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        connections[chat_id].remove(websocket)


# Функция для отправки события в WebSocket
async def broadcast(chat_id: int, message: dict):
    for ws in connections.get(chat_id, []):
        logging.info(f"Подключение {ws}, сообщение {message}")
        await ws.send_json(message)

class ChatMessage(BaseModel):
    user_id: int
    message: str
    chat_id: int


class BotMessage(BaseModel):
    chat_id: int
    message: dict

@app.post("/internal/bot_message")
async def receive_bot_message(bot_msg: BotMessage):
    """Получаем сообщения от бота через DB Consumer и отправляем через WebSocket"""
    logging.info(f"Получено сообщение от бота для chat_id={bot_msg.chat_id}: {bot_msg.message}")

    # Отправляем сообщение через WebSocket всем клиентам в чате
    await broadcast(bot_msg.chat_id, bot_msg.message)


@app.on_event("startup")
async def startup():
    global service_message_alive
    service_message_alive = True
    await db.init_db_pool()

@app.on_event("shutdown")
async def shutdown():
    global service_message_alive
    service_message_alive = False
    await db.pool.close()

@app.post("/send_message")
async def send_message(chat: ChatMessage):
    message = {
        "user_id": chat.user_id,
        "chat_id": chat.chat_id,
        "message": chat.message,
        "is_from_bot": False
    }
    logging.info(f"Отравили в сокет внутри chat_app")
    # отправляем пользователю сразу
    await broadcast(chat.chat_id, message)
    # отправка в Kafka
    producer.send("chat-messages", key=chat.user_id, value=message)
    producer.flush()

    return {"status": "ok"}



@app.get("/chat/{chat_id}/messages")
async def get_chat_messages(chat_id: int, limit: int = 50, offset: int = 0,  username: str = Depends(get_current_user_from_cookie)):
    try:
        messages = await db.get_chat_messages(chat_id, username, limit=limit, offset=offset)
        return {
            "chat_id": chat_id,
            "total": len(messages),
            "messages": messages,
            "username": username
        }
    except Exception as e:
        logging.error(f"Ошибка в эндпоинте: {e}")
        raise HTTPException(status_code=500, detail="Не удалось загрузить историю чата")

@app.get("/user/all/messages")
async def get_all_user_messages(limit: int = 50, offset: int = 0,  username: str = Depends(get_current_user_from_cookie)):
    try:
        messages = await db.get_all_user_messages(username, limit=limit, offset=offset)
        return {"messages": messages}
    except Exception as e:
        logging.error(f"Ошибка в эндпоинте: {e}")
        raise HTTPException(status_code=500, detail="Не удалось загрузить историю чата")


@app.post("/chat/new")
async def create_chat(data: dict):
    user_id = data.get("user_id")
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id required")

    chat_id = await db.create_new_chat()

    # (опционально) создаём первое сообщение
    await db.add_message(
        username=user_id,
        message="Чат создан",
        chat_id=chat_id,
        is_from_bot=True
    )

    return {"chat_id": chat_id}



@app.get("/health")
async def health():
    status = "ok" if service_message_alive else "error"
    return {"service": "llm-bot", "status": status}


import uvicorn
from utils.config import PORT_CHATS_SERVICE

if __name__ == "__main__":
    uvicorn.run("chats_service.app:app", host="127.0.0.1", port=int(PORT_CHATS_SERVICE), reload=True)


