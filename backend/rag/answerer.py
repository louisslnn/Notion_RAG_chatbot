from typing import List

from langchain.chat_models import init_chat_model
from pydantic import BaseModel, Field
from dotenv import load_dotenv, find_dotenv

from .prompts import ANSWER_PROMPT

load_dotenv(find_dotenv())

DEFAULT_MODEL = "anthropic:claude-3-5-sonnet-latest"


class AnswerOutput(BaseModel):
    answer: str = Field(description="Final natural language answer based on context")


class AnswerGenerator:
    def __init__(self, model_name: str = DEFAULT_MODEL, temperature: float = 0.2):
        self.llm = init_chat_model(model_name, temperature=temperature)

    def generate(self, question: str, chunks: List[str]) -> str:
        numbered_context = "\n\n".join(f"(chunk {i + 1}) {c}" for i, c in enumerate(chunks))
        prompt = ANSWER_PROMPT.format(question=question, context=numbered_context)
        response = self.llm.with_structured_output(AnswerOutput).invoke(
            [{"role": "user", "content": prompt}]
        )
        return response.answer

