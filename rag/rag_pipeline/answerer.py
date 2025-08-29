from pydantic import BaseModel, Field
from typing import List
from prompts import ANSWER_PROMPT
from langchain.chat_models import init_chat_model
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

ANTHROPIC_MODEL = "anthropic:claude-3-5-sonnet-latest"

llm = init_chat_model(ANTHROPIC_MODEL, temperature=0.3)  

class AnswerOutput(BaseModel):
    answer: str = Field(description="Final natural language answer based on context")

def generate_answer(question: str, chunks: List[str]) -> str:
    # build a single context string with numbered chunks to keep track
    numbered_context = "\n\n".join(f"(chunk {i+1}) {c}" for i, c in enumerate(chunks))
    prompt = ANSWER_PROMPT.format(question=question, context=numbered_context)
    resp = llm.with_structured_output(AnswerOutput).invoke([{"role":"user","content":prompt}])
    return resp.answer