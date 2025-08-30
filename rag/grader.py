from pydantic import BaseModel, Field
from prompts import GRADE_PROMPT
from langchain.chat_models import init_chat_model
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

ANTHROPIC_MODEL = "anthropic:claude-3-5-sonnet-latest"

llm = init_chat_model(ANTHROPIC_MODEL, temperature=0.3)  
grader_llm = init_chat_model(ANTHROPIC_MODEL, temperature=0.3)

class GradeDocuments(BaseModel):
    binary_score: str = Field(
        description="Relevance score: 'yes' if relevant, or 'no' if not relevant"
    )

def grade_context(question: str, context_text: str) -> str:
    prompt = GRADE_PROMPT.format(question=question, context=context_text)
    resp = grader_llm.with_structured_output(GradeDocuments).invoke([{"role":"user","content":prompt}])
    return resp.binary_score  # "yes" or "no"