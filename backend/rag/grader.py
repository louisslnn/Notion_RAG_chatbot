from langchain.chat_models import init_chat_model
from pydantic import BaseModel, Field
from dotenv import load_dotenv, find_dotenv

from .prompts import GRADE_PROMPT

load_dotenv(find_dotenv())

DEFAULT_MODEL = "anthropic:claude-3-5-sonnet-latest"


class GradeDocuments(BaseModel):
    binary_score: str = Field(description="Return 'yes' when relevant, 'no' otherwise.")


class ContextGrader:
    def __init__(self, model_name: str = DEFAULT_MODEL, temperature: float = 0.0):
        self.llm = init_chat_model(model_name, temperature=temperature)

    def grade(self, question: str, context_text: str) -> str:
        prompt = GRADE_PROMPT.format(question=question, context=context_text)
        response = self.llm.with_structured_output(GradeDocuments).invoke(
            [{"role": "user", "content": prompt}]
        )
        return response.binary_score

