from fastapi import FastAPI, HTTPException, Request
import httpx
import logging

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="API Gateway")

# Настройки маршрутов
SERVICES = {
    "auth": "http://localhost:8000",
    "chats": "http://localhost:7000",
}

@app.post("/auth/{path:path}")
async def auth_proxy(request: Request, path: str):
    async with httpx.AsyncClient() as client:
        url = f"{SERVICES['auth']}/{path}"
        response = await client.request(
            method=request.method,
            url=url,
            headers=dict(request.headers),
            content=await request.body(),
            timeout=30.0
        )
        return response.json()

@app.post("/chats/{path:path}")
@app.get("/chats/{path:path}")
async def chats_proxy(request: Request, path: str):
    async with httpx.AsyncClient() as client:
        url = f"{SERVICES['chats']}/{path}"
        response = await client.request(
            method=request.method,
            url=url,
            headers=dict(request.headers),
            content=await request.body(),
            timeout=30.0
        )
        return response.json()

@app.get("/")
async def root():
    return {"gateway": "running", "services": SERVICES}