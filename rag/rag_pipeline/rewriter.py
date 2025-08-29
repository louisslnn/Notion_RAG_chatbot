from pydantic import BaseModel, Field
from prompts import REWRITE_PROMPT
from langchain.chat_models import init_chat_model
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

ANTHROPIC_MODEL = "anthropic:claude-3-5-sonnet-latest"

llm = init_chat_model(ANTHROPIC_MODEL, temperature=0.3)  

class RewrittenQuestion(BaseModel):
    rewritten: str = Field(description="A clearer, more specific question")

def rewrite_query(original_query: str) -> str:
    prompt = REWRITE_PROMPT.format(question=original_query)
    resp = llm.with_structured_output(RewrittenQuestion).invoke([{"role":"user","content":prompt}])
    return resp.rewritten