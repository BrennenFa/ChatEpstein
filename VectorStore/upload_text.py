import hashlib
from typing import List, Dict
from langchain_core.documents import Document


def generate_id(s3_key: str, page_number: int, chunk_text: str) -> str:
    """
    Generates a deterministic ID for a chunk.

    Args:
        s3_key: S3 key of the source file
        page_number: Page number in the document
        chunk_text: The text content of the chunk

    Returns:
        MD5 hash as a unique identifier
    """
    unique_input = f"{s3_key}_p{page_number}_{chunk_text}"
    hash_obj = hashlib.md5(unique_input.encode('utf-8'))
    return hash_obj.hexdigest()


def upload_chunks_to_chroma(chunks: List[Dict], s3_key: str, vector_db) -> int:
    """
    Upload text chunks to vector database with deterministic IDs for idempotency.

    Args:
        chunks: List of dicts with 'text' and 'metadata' keys
        s3_key: S3 key of the source file (used for ID generation)
        vector_db: Vector store instance (Pinecone, ChromaDB, etc.)

    Returns:
        Number of chunks uploaded
    """
    if not chunks:
        return 0

    # Create Document objects
    documents = [
        Document(
            page_content=chunk["text"],
            metadata=chunk["metadata"]
        )
        for chunk in chunks
    ]

    # Generate deterministic IDs for idempotency (updates instead of duplicates)
    ids = [
        generate_id(s3_key, chunk["metadata"]["page_number"], chunk["text"])
        for chunk in chunks
    ]

    # Upload to vector database (both Pinecone and ChromaDB)
    vector_db.add_documents(documents, ids=ids)

    return len(chunks)
