import uvicorn

if __name__ == "__main__":
    uvicorn.run("chats_service.app:app", host="127.0.0.1", port=7000, reload=True)
