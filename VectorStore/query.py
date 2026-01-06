from pinecone_connect import pinecone_connect
from llm import get_llm
from typing import List, Dict, Optional, Literal

from langchain.chains import RetrievalQA
from langchain.prompts import PromptTemplate
from langchain_core.documents import Document


class RAGQueryEngine:
    def __init__(
        self,
        llm_provider: Optional[Literal["anthropic", "openai", "ollama"]] = None,
        llm_model: Optional[str] = None
    ):
        """
        Initialize the RAG query engine with LangChain.

        Args:
            llm_provider: LLM provider (optional, for RAG responses)
            llm_model: Specific model name (optional)
        """

        self.vector_db = pinecone_connect()
        self.retriever = self.vector_db.as_retriever(search_kwargs={"k": 5})

        self.llm = None
        self.qa_chain = None

        if llm_provider:
            self.llm = get_llm(provider=llm_provider, model_name=llm_model)
            self._setup_qa_chain()

        print(f"Connected to Pinecone vector database")

    def _setup_qa_chain(self):
        """Setup the RetrievalQA chain with custom prompt."""
        prompt_template = """You are an assistant helping researchers analyze Epstein-related documents.
Use the following pieces of context to answer the question. If you don't know the answer based on the context, say so.
Always cite the source document ID and page number when possible.

Context:
{context}

Question: {question}

Answer:"""

        PROMPT = PromptTemplate(
            template=prompt_template,
            input_variables=["context", "question"]
        )

        self.qa_chain = RetrievalQA.from_chain_type(
            llm=self.llm,
            chain_type="stuff",
            retriever=self.retriever,
            return_source_documents=True,
            chain_type_kwargs={"prompt": PROMPT}
        )

    def search(
        self,
        query: str,
        k: int = 5,
        filter: Optional[Dict] = None
    ) -> List[Document]:
        """
        Search for relevant documents using LangChain retriever.

        Args:
            query: Search query string
            k: Number of results to return
            filter: Metadata filter dict (e.g., {"source": "DOJ"})

        Returns:
            List of LangChain Documents with metadata
        """
        search_kwargs = {"k": k}
        if filter:
            search_kwargs["filter"] = filter

        retriever = self.vector_db.as_retriever(search_kwargs=search_kwargs)
        return retriever.get_relevant_documents(query)

    def ask(self, question: str) -> Dict:
        """
        Ask a question and get an LLM-generated answer with sources.

        Args:
            question: Question to ask

        Returns:
            Dict with 'answer' and 'source_documents'
        """
        if not self.qa_chain:
            raise ValueError("LLM not initialized. Pass llm_provider to __init__")

        result = self.qa_chain({"query": question})
        return {
            "answer": result["result"],
            "source_documents": result["source_documents"]
        }

    def get_context_for_llm(self, query: str, k: int = 3) -> str:
        """
        Get formatted context string for external LLM use.

        Args:
            query: Search query
            k: Number of results to include

        Returns:
            Formatted context string with document excerpts
        """
        docs = self.search(query, k=k)

        if not docs:
            return "No relevant documents found."

        context_parts = []
        for i, doc in enumerate(docs, start=1):
            context_parts.append(
                f"[Document {i}]\n"
                f"Source: {doc.metadata.get('source', 'Unknown')}\n"
                f"Document ID: {doc.metadata.get('document_id', 'Unknown')}\n"
                f"Page: {doc.metadata.get('page_number', 'Unknown')}\n"
                f"Content:\n{doc.page_content}\n"
            )

        return "\n---\n".join(context_parts)


# if __name__ == "__main__":
#     # Initialize the query engine
#     engine = RAGQueryEngine(
#         llm_provider="anthropic",
#         llm_model="claude-3-5-sonnet-20241022"
#     )

#     # Example 1: Search for relevant documents
#     query = "flight logs"
#     results = engine.search(query, k=3)
#     print(f"Found {len(results)} results for '{query}':")
#     for i, doc in enumerate(results, 1):
#         print(f"\n{i}. {doc.metadata.get('document_id')} (Page {doc.metadata.get('page_number')})")
#         print(f"   {doc.page_content[:200]}...")

#     # Example 2: Ask a question with LLM
#     question = "What information is available about flight logs?"
#     result = engine.ask(question)
#     print(f"\n\nQuestion: {question}")
#     print(f"Answer: {result['answer']}")

#     # Example 3: Get context for external LLM use
#     context = engine.get_context_for_llm("depositions", k=2)
#     print(f"\n\nContext for external LLM:\n{context[:500]}...")
