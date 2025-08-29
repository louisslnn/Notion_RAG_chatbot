from langchain_core.vectorstores import InMemoryVectorStore
from langchain.tools.retriever import create_retriever_tool

class Retriever:
    def __init__(self, doc_splits, embedding_function):
        self.vectorstore = InMemoryVectorStore.from_documents(
            documents=doc_splits, embedding=embedding_function
            )
        self.retriever = self.vectorstore.as_retriever()

    def get_answer(self, query: str):
        retriever_tool = create_retriever_tool(
            self.retriever,
            "course_material_search",
            """
            Search and return information about McGill's courses course material 
            (in various fields such as Math, Data Science, Management, Economics).
            """
        )
        return retriever_tool.invoke({"query": query})
    
