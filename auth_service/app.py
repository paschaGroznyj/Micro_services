import logging
import asyncio
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from datetime import datetime, timedelta
from auth_service.create_tables import DataBase
from utils.config import SECRET_KEY, ALGORITHM

ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Настройка логов
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# Инициализация
app = FastAPI(title="Auth Service")
db = DataBase()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")


@app.on_event("startup")
async def startup():
    await db.init_db_pool()


def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


@app.post("/register")
async def register(username: str, password: str):
    user_id = await db.add_user(username, password)
    if user_id:
        return {"msg": f"Пользователь {username} зарегистрирован", "user_id": user_id}
    raise HTTPException(status_code=400, detail="Пользователь уже существует")


@app.post("/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    # Проверка пользователя
    is_valid = await db.check_user_password(form_data.username, form_data.password)
    if not is_valid:
        raise HTTPException(status_code=401, detail="Неверный логин или пароль")
    else:
        print("Пользователь зашел")
    # Генерация токена
    access_token = create_access_token({"sub": form_data.username})
    return {"access_token": access_token, "token_type": "bearer"}


@app.get("/me")
async def read_users_me(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Неверный токен")
    except JWTError:
        raise HTTPException(status_code=401, detail="Неверный токен")

    return {"username": username}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main_auth:app", host="localhost", port=8000, reload=True)