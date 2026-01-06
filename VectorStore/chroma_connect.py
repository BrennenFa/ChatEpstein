from langchain_chroma import Chroma
from langchain_core.documents import Document
from pathlib import Path
from langchain_huggingface import HuggingFaceEmbeddings
import os
from dotenv import load_dotenv

load_dotenv()


def chroma_connect(
    collection_name: str = "epstein_docs",
) -> Chroma:
    """
    Get Chroma vector store with HuggingFace embeddings.

    Args:
        collection_name: Name of the collection

    Returns:
        Chroma vector store instance
    """
    persist_directory = os.getenv("DB_DIR")
    if not persist_directory:
        raise ValueError("DB_DIR not found in environment variables")
    persist_dir = Path(persist_directory)
    persist_dir.mkdir(parents=True, exist_ok=True)

    model = "BAAI/bge-base-en-v1.5"
    embeddings = HuggingFaceEmbeddings(
            model_name=model,
            model_kwargs={'device': 'cpu'},
            encode_kwargs={'normalize_embeddings': True, 'batch_size': 32}
    )
    
    print(f"Initializing Chroma vector store: {collection_name}")
    database = Chroma(
        collection_name=collection_name,
        embedding_function=embeddings,
        persist_directory=str(persist_dir),
        collection_metadata={"hnsw:space": "cosine"}
    )
    print(f"Vector store ready. Documents: {database._collection.count()}")
    return database


# if __name__ == "__main__":
#     vector_store = chroma_connect(persist_directory="./test_chroma_db")

#     test_docs = [
#         Document(
#             page_content="Sample document 1 about flight logs",
#             metadata={"document_id": "TEST-001", "source": "DOJ"}
#         ),
#         Document(
#             page_content="Sample document 2 about depositions",
#             metadata={"document_id": "TEST-002", "source": "HC"}
#         )
#     ]

#     vector_store.add_documents(test_docs)
#     print(f"\nAdded {len(test_docs)} documents")

#     results = vector_store.similarity_search("flight logs", k=2)
#     print(f"\nQuery results: {len(results)} documents")
#     for doc in results:
#         print(f"  - {doc.page_content[:50]}... | {doc.metadata}")
