import re

from dotenv import find_dotenv, load_dotenv
from langchain.chat_models import init_chat_model
from pydantic import BaseModel, Field

from .prompts import CONDENSE_PROMPT, REWRITE_PROMPT

load_dotenv(find_dotenv())

# Query rewriting is cheap and latency-sensitive: use Haiku.
DEFAULT_MODEL = "claude-haiku-4-5"

# Below this many words a question is considered too terse to embed well.
SHORT_QUESTION_WORDS = 6

# Pronouns and follow-up markers that only make sense with prior context.
_ANAPHORIC_WORDS = (
    # French
    "il|elle|ils|elles|ça|cela|celui|celle|ceux|celles|lui|leur|dessus|celui-ci|celle-ci"
    # English
    "|it|this|that|these|those|they|them|he|she|its|their"
)
_ANAPHORIC_RE = re.compile(
    rf"(?:\b(?:{_ANAPHORIC_WORDS})\b)"
    r"|(?:^\s*(?:et|and)\b)"
    r"|(?:\b(?:et pour|and for|what about|qu'en est-il)\b)",
    re.IGNORECASE,
)


def rewrite_reason(question: str) -> str | None:
    """Why this question needs rewriting: 'short', 'anaphoric', or None."""
    if len(re.findall(r"\w+", question)) < SHORT_QUESTION_WORDS:
        return "short"
    if _ANAPHORIC_RE.search(question):
        return "anaphoric"
    return None


class RewrittenQuestion(BaseModel):
    rewritten: str = Field(description="A clearer, more specific question")


class QueryRewriter:
    def __init__(self, model_name: str = DEFAULT_MODEL, temperature: float = 0.2):
        self.llm = init_chat_model(model_name, model_provider="anthropic", temperature=temperature)

    def _invoke(self, prompt: str) -> str:
        response = self.llm.with_structured_output(RewrittenQuestion).invoke(
            [{"role": "user", "content": prompt}]
        )
        return response.rewritten

    def rewrite(self, original_query: str) -> str:
        return self._invoke(REWRITE_PROMPT.format(question=original_query))

    def condense(self, question: str, history: list[dict]) -> str:
        """Fold an anaphoric follow-up + history into a standalone question."""
        transcript = "\n".join(f"{msg['role']}: {msg['content']}" for msg in history)
        return self._invoke(CONDENSE_PROMPT.format(history=transcript, question=question))
