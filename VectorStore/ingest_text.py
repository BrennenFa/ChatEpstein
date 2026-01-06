import boto3
import io
import os
from pathlib import Path
from dotenv import load_dotenv
from tqdm import tqdm
from typing import Dict
from concurrent.futures import ThreadPoolExecutor, as_completed

from chunking import DocumentChunker
from upload_text import upload_chunks_to_chroma
from ingest_pdfs import extract_date_from_filename

load_dotenv()

bucket_name = os.getenv("AWS_BUCKET_NAME")
region = os.getenv("AWS_REGION")

s3 = boto3.client('s3', region_name=region)

class TextIngestionPipeline:
    def __init__(self, source_dict: Dict[str, str], vector_db):
        """
        Initialize the Text ingestion pipeline.

        Args:
            source_dict: Dictionary mapping source codes to descriptions
            vector_db: Initialized vector database instance
        """
        self.source_dict = source_dict
        self.chunker = DocumentChunker(chunk_size=1024, chunk_overlap=200)
        self.vector_db = vector_db

    def extract_text_from_txt(self, text_bytes: bytes, document_id: str) -> str:
        """
        Extract text from .txt file bytes.

        Args:
            text_bytes: Text file content as bytes
            document_id: Unique identifier for the document

        Returns:
            Decoded text content
        """
        try:
            # Try UTF-8 first, fall back to latin-1 if that fails
            try:
                text = text_bytes.decode('utf-8')
            except UnicodeDecodeError:
                text = text_bytes.decode('latin-1')

            return text.strip()

        except Exception as e:
            print(f"[Text] Error extracting text from {document_id}: {e}")
            return ""

    def process_text(self, s3_key: str, source: str) -> int:
        """
        Process a single text file: download, extract, chunk, embed, store.

        Args:
            s3_key: S3 key of the text file
            source: Source identifier

        Returns:
            Number of chunks added to vector db
        """
        document_id = Path(s3_key).stem
        file_name = Path(s3_key).name

        try:
            # connect to s3
            response = s3.get_object(Bucket=bucket_name, Key=s3_key)
            text_bytes = response['Body'].read()

            # extract text
            text = self.extract_text_from_txt(text_bytes, document_id)

            if not text:
                print(f"[Text] No text extracted from {document_id}")
                return 0

            publication_date = extract_date_from_filename(file_name)

            # metadata for storage
            base_metadata = {
                "document_id": document_id,
                "source": self.source_dict[source],
                "s3_key": s3_key,
                "file_name": file_name,
                "document_type": "text",
                "total_pages": 1,
                "publication_date": publication_date if publication_date else "Unknown"
            }

            # chunk the extracted text
            chunks = self.chunker.chunk_page(
                page_text=text,
                page_number=1,
                base_metadata=base_metadata
            )

            if not chunks:
                return 0

            # Upload chunks to vector db with idempotency
            chunks_added = upload_chunks_to_chroma(chunks, s3_key, self.vector_db)

            return chunks_added

        except Exception as e:
            print(f"[Text] Error processing {s3_key}: {e}")
            return 0

    def ingest_from_s3(self, s3_prefix: str, source: str, limit: int = None, max_workers: int = 4):
        """
        Ingest text files from S3 into vector db.

        Args:
            s3_prefix: S3 prefix to search (e.g., "HC_organized/documents/")
            source: Source identifier
            limit: Optional limit on number of text files to process
            max_workers: Maximum number of parallel workers (default: 4)
        """
        print(f"[Text] Listing text files from s3://{bucket_name}/{s3_prefix}...")

        paginator = s3.get_paginator('list_objects_v2')
        pages = paginator.paginate(Bucket=bucket_name, Prefix=s3_prefix)

        # find text files
        text_keys = []
        for page in pages:
            if 'Contents' in page:
                for obj in page['Contents']:
                    if obj['Key'].lower().endswith('.txt'):
                        text_keys.append(obj['Key'])

        if limit:
            text_keys = text_keys[:limit]

        print(f"[Text] {len(text_keys)} text files to process")

        total_chunks = 0
        # process text files with threads
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # keep a record of tasks with executor, using s3_key as identifier
            future_to_key = {
                executor.submit(self.process_text, s3_key, source): s3_key
                for s3_key in text_keys
            }

            # collect results with progress bar
            for future in tqdm(as_completed(future_to_key), total=len(text_keys), desc="Processing Text Files"):
                chunks_added = future.result()
                total_chunks += chunks_added

        print(f"\n[Text] {'='*50}")
        print(f"[Text] Ingestion complete!")
        print(f"[Text] {'='*50}")
        print(f"[Text] Text files processed: {len(text_keys)}")
        print(f"[Text] Total chunks added: {total_chunks}")

        # Get Pinecone index stats
        stats = self.vector_db._index.describe_index_stats()
        total_vectors = stats.get('total_vector_count', 0)
        print(f"[Text] Total documents in store: {total_vectors:,}")
