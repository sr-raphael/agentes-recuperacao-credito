import logging

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI

from app.api.deps import get_coordinator
from app.api.negotiation_rest import NegotiationRestApi

load_dotenv()

logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="AI Debt Negotiator API",
    description="Sistema multi-agente para negociação de dívidas",
    version="1.0.0",
)

NegotiationRestApi(get_coordinator).mount(app)


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
