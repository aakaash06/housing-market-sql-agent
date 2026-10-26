"""Minimal HTTP API.  Run: uvicorn api:app --reload   then POST /ask {"question": "..."}"""

from fastapi import FastAPI
from pydantic import BaseModel

from agent import HousingAgent

app = FastAPI(title="Housing Market SQL Agent")
agent = HousingAgent()


class AskRequest(BaseModel):
    question: str


@app.post("/ask")
def ask(req: AskRequest) -> dict:
    return agent.ask(req.question).to_dict()


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "model": agent.model}
