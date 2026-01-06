from langchain_pinecone import PineconeVectorStore
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
from pinecone import Pinecone, ServerlessSpec
import os
from dotenv import load_dotenv
import time

load_dotenv()


def pinecone_connect(
    index_name: str = "epstein-files",
) -> PineconeVectorStore:
    """
    Get Pinecone vector store with HuggingFace embeddings.

    Args:
        index_name: Name of the Pinecone index

    Returns:
        PineconeVectorStore instance
    """
    # Get API key from environment
    api_key = os.getenv("PINECONE_API_KEY")
    if not api_key:
        raise ValueError("PINECONE_API_KEY not found in environment variables")

    # Initialize Pinecone client
    pc = Pinecone(api_key=api_key)

    # check if index exists, create if not 
    existing_indexes = [index.name for index in pc.list_indexes()]

    if index_name not in existing_indexes:
        print(f"Creating new Pinecone index: {index_name}")
        pc.create_index(
            name=index_name,
            dimension=768,
            metric="cosine",
            spec=ServerlessSpec(
                cloud="aws",
                region="us-east-1"
            )
        )
        # wait for index to be ready
        while not pc.describe_index(index_name).status['ready']:
            time.sleep(1)
        print(f"Index {index_name} created and ready!")

    # Initialize embeddings 
    model = "BAAI/bge-base-en-v1.5"
    embeddings = HuggingFaceEmbeddings(
        model_name=model,
        model_kwargs={'device': 'cpu'},
        encode_kwargs={'normalize_embeddings': True, 'batch_size': 32}
    )

    print(f"Connecting to Pinecone index: {index_name}")

    # Create LangChain Pinecone vector store
    vectorstore = PineconeVectorStore(
        index_name=index_name,
        embedding=embeddings,
        pinecone_api_key=api_key
    )

    # get index stats
    index = pc.Index(index_name)
    stats = index.describe_index_stats()
    total_vectors = stats.get('total_vector_count', 0)

    print(f"Vector store ready. Documents: {total_vectors:,}")
    return vectorstore


if __name__ == "__main__":
    try:
        vector_store = pinecone_connect()
        print("\nSuccessfully connected to Pinecone!")


    except Exception as e:
        print(f"\nError: {e}")