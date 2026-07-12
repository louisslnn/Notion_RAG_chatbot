import os

from dotenv import find_dotenv, load_dotenv
from langchain.chat_models import init_chat_model
from pydantic import BaseModel, Field

from .prompts import ANSWER_PROMPT

load_dotenv(find_dotenv())

# The answering model is the quality-sensitive step; make it configurable.
DEFAULT_MODEL = os.getenv("ANSWER_MODEL", "claude-sonnet-4-6")


class AnswerOutput(BaseModel):
    answer: str = Field(description="Final natural language answer based on context")


class AnswerGenerator:
    def __init__(self, model_name: str = DEFAULT_MODEL, temperature: float = 0.2):
        self.llm = init_chat_model(model_name, model_provider="anthropic", temperature=temperature)

    @staticmethod
    def _prompt(question: str, chunks: list[str]) -> str:
        numbered_context = "\n\n".join(f"(chunk {i + 1}) {c}" for i, c in enumerate(chunks))
        return ANSWER_PROMPT.format(question=question, context=numbered_context)

    def generate(self, question: str, chunks: list[str]) -> str:
        response = self.llm.with_structured_output(AnswerOutput).invoke(
            [{"role": "user", "content": self._prompt(question, chunks)}]
        )
        return response.answer

    def generate_stream(self, question: str, chunks: list[str]):
        """Yield the answer as text deltas (no structured output when streaming)."""
        for message_chunk in self.llm.stream(
            [{"role": "user", "content": self._prompt(question, chunks)}]
        ):
            content = message_chunk.content
            if isinstance(content, list):
                content = "".join(
                    part.get("text", "") if isinstance(part, dict) else str(part)
                    for part in content
                )
            if content:
                yield content
