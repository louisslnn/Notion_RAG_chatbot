from langchain.chat_models import init_chat_model
from pydantic import BaseModel, Field
from dotenv import load_dotenv, find_dotenv

from .prompts import REWRITE_PROMPT

load_dotenv(find_dotenv())

DEFAULT_MODEL = "anthropic:claude-3-5-sonnet-latest"


class RewrittenQuestion(BaseModel):
    rewritten: str = Field(description="A clearer, more specific question")


class QueryRewriter:
    def __init__(self, model_name: str = DEFAULT_MODEL, temperature: float = 0.2):
        self.llm = init_chat_model(model_name, temperature=temperature)

    def rewrite(self, original_query: str) -> str:
        prompt = REWRITE_PROMPT.format(question=original_query)
        response = self.llm.with_structured_output(RewrittenQuestion).invoke(
            [{"role": "user", "content": prompt}]
        )
        return response.rewritten

