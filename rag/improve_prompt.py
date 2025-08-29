from langchain.chat_models import init_chat_model
from dotenv import load_dotenv

load_dotenv()

# Initialize your model
response_model = init_chat_model("anthropic:claude-3-5-sonnet-latest", temperature=0)

# Minimal state-like dict instead of importing MessagesState
state = {
    "messages": [
        {"role": "user", "content": "Hello, how are you?"}
    ]
}
def generate_query_or_respond(state):
    """
    Calls the model to respond based on the current messages.
    """
    response = response_model.invoke(state["messages"])
    return {"messages": [{"role": "assistant", "content": response}]}  # mimic MessagesState

input = {
    "messages": [
        {
            "role": "user",
            "content": "What does Lilian Weng say about types of reward hacking?",
        }
    ]
}
print(generate_query_or_respond(input)["messages"][-1]["content"])