from dotenv import find_dotenv, load_dotenv
from langchain.chat_models import init_chat_model
from pydantic import BaseModel, Field

from .prompts import REWRITE_PROMPT

load_dotenv(find_dotenv())

# Query rewriting is cheap and latency-sensitive: use Haiku.
DEFAULT_MODEL = "claude-haiku-4-5"


class RewrittenQuestion(BaseModel):
    rewritten: str = Field(description="A clearer, more specific question")


class QueryRewriter:
    def __init__(self, model_name: str = DEFAULT_MODEL, temperature: float = 0.2):
        self.llm = init_chat_model(model_name, model_provider="anthropic", temperature=temperature)

    def rewrite(self, original_query: str) -> str:
        prompt = REWRITE_PROMPT.format(question=original_query)
        response = self.llm.with_structured_output(RewrittenQuestion).invoke(
            [{"role": "user", "content": prompt}]
        )
        return response.rewritten
