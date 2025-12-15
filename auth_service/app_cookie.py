import logging
from pathlib import Path
from fastapi import FastAPI, Depends, HTTPException
from contextlib import asynccontextmanager
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from fastapi import FastAPI, Depends, HTTPException, Request, Form, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from datetime import datetime, timedelta
from auth_service.db_scripts.users_tables import DataBaseUser
from utils.config import SECRET_KEY, ALGORITHM
from fastapi.templating import Jinja2Templates
from utils.config import HOST_CHATS_SERVICE

ACCESS_TOKEN_EXPIRE_MINUTES = 30
BASE_DIR = Path(__file__).parent

# Настройка логов
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# Инициализация

db = DataBaseUser()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await db.init_db_pool()
    yield
    # Shutdown
    await db.pool.close()

app = FastAPI(title="Auth Service", lifespan=lifespan)
# @app.on_event("startup")
# async def startup():
#     await db.init_db_pool()
#
# @app.on_event("shutdown")
# async def shutdown():
#     await db.pool.close()
# app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

# === HTML-страницы ===
@app.get("/login-page", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.get("/register-page", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})


# === Web-обработчики (не API!) ===
@app.post("/login-web", response_class=RedirectResponse)
async def login_web(username: str = Form(...), password: str = Form(...)):
    is_valid = await db.check_user_password(username, password)
    if not is_valid:
        # Возвращаем на форму с ошибкой
        return templates.TemplateResponse(
            "login.html",
            {"request": {}, "error": "Неверный логин или пароль"},
            status_code=401
        )
    # Генерируем токен
    access_token = create_access_token({"sub": username})
    # Сохраняем токен в cookie (удобно для браузера)
    response = RedirectResponse(url=f"http://localhost:{HOST_CHATS_SERVICE}/chat/3", status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(key="access_token", value=f"Bearer {access_token}", httponly=True)
    return response


@app.post("/register-web", response_class=HTMLResponse)
async def register_web(request: Request, username: str = Form(...), password: str = Form(...)):
    try:
        user_id = await db.add_user(username, password)
        if user_id:
            return templates.TemplateResponse(
                "login.html",
                {"request": request, "error": f"Пользователь {username} создан. Теперь войдите."}
            )
        else:
            raise ValueError("Пользователь уже существует")
    except Exception:
        return templates.TemplateResponse(
            "register.html",
            {"request": request, "error": "Пользователь уже существует"},
            status_code=400
        )



@app.post("/register")
async def register(form_data: OAuth2PasswordRequestForm = Depends()):
    user_id = await db.add_user(form_data.username, form_data.password)
    if user_id:
        return {"msg": f"Пользователь {form_data.username} зарегистрирован", "user_id": user_id}
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

import uvicorn
from utils.config import HOST_AUTH_SERVICE

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=int(HOST_AUTH_SERVICE), reload=True)