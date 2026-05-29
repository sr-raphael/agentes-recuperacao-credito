import logging
from pathlib import Path

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.api.deps import get_coordinator
from app.api.negotiation_rest import NegotiationRestApi

load_dotenv()

logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="AI Debt Negotiator API",
    description="Sistema multi-agente para negociação de dívidas",
    version="1.0.0",
)

CHAT_STATIC_DIR = Path(__file__).resolve().parent / "static" / "chat"
app.mount("/static/chat", StaticFiles(directory=str(CHAT_STATIC_DIR)), name="chat-static")

NegotiationRestApi(get_coordinator).mount(app)


@app.get("/")
def root_redirect():
    return RedirectResponse(url="/chat", status_code=302)


@app.get("/chat")
def chat_page():
    return FileResponse(CHAT_STATIC_DIR / "index.html")


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
