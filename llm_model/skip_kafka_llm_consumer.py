import json
import logging
from kafka import KafkaConsumer, KafkaProducer
from utils.config import KAFKA_BROKER
from llm_model.giga_chat import GigaChatApi  # твой класс
from utils.config import API_GIGACHAT

logging.basicConfig(level=logging.INFO)

# Инициализация
llm = GigaChatApi(API_GIGACHAT)

producer = KafkaProducer(
    bootstrap_servers=[KAFKA_BROKER],
    api_version=(4,1,0),
    key_serializer=lambda k: str(k).encode('utf-8'),
    value_serializer=lambda m: json.dumps(m).encode('utf-8'))

consumer = KafkaConsumer(
    'chat-messages',
    bootstrap_servers=['localhost:9092'],
    group_id='llm-bot-group',  # ← обязательно отличается от DB consumer'а!
    value_deserializer=lambda m: json.loads(m.decode('utf-8')),
    auto_offset_reset='latest'
)

logging.info("LLM-бот запущен и ждёт сообщения...")

for message in consumer:
    payload = message.value
    user_id = payload.get("user_id")
    chat_id = payload.get("chat_id")
    text = payload.get("message")
    is_from_bot = payload.get("is_from_bot", False)

    # Пропускаем сообщения от бота (защита от петли)
    if is_from_bot or user_id == -1:
        continue

    if not text or chat_id is None:
        logging.warning(f"Некорректное сообщение: {payload}")
        continue

    try:
        # Генерация ответа
        response_text = llm.take_answer(text)  # или dummy_answer для теста

        # Формируем сообщение от бота
        bot_message = {
            "user_id": -1,  # специальный ID для бота
            "chat_id": chat_id,
            "message": response_text,
            "is_from_bot": True
        }

        # Отправляем в Kafka
        producer.send("chat-messages", value=bot_message)
        producer.flush()
        logging.info(f"Отправлен ответ бота в чат {chat_id}: {response_text[:50]}...")

    except Exception as e:
        logging.error(f"Ошибка в LLM-боте: {e}")