import boto3
import pdfplumber
import io
import os
import re
from pathlib import Path
from dotenv import load_dotenv
from tqdm import tqdm
from typing import List, Dict, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from chunking import DocumentChunker
from upload_text import upload_chunks_to_chroma

load_dotenv()

bucket_name = os.getenv("AWS_BUCKET_NAME")
region = os.getenv("AWS_REGION")

s3 = boto3.client('s3', region_name=region)


def extract_date_from_filename(filename: str) -> Optional[str]:
    """
    Extract publication date from filename or return None.

    Looks for patterns like:
    - YYYY-MM-DD (2003-07-15)
    - YYYY_MM_DD (2003_07_15)
    - YYYYMMDD (20030715)
    - Month DD, YYYY (July 15, 2003)

    Args:
        filename: Document filename

    Returns:
        Date string in YYYY-MM format or None
    """
    # Pattern 1: YYYY-MM-DD or YYYY_MM_DD
    match = re.search(r'(\d{4})[-_](\d{2})[-_](\d{2})', filename)
    if match:
        return f"{match.group(1)}-{match.group(2)}"

    # Pattern 2: YYYYMMDD
    match = re.search(r'(\d{4})(\d{2})(\d{2})', filename)
    if match:
        return f"{match.group(1)}-{match.group(2)}"

    # Pattern 3: Just year (YYYY)
    match = re.search(r'(19\d{2}|20\d{2})', filename)
    if match:
        return match.group(1)

    return None


class PDFIngestionPipeline:
    def __init__(self, source_dict: Dict[str, str], vector_db):
        """
        Initialize the PDF ingestion pipeline.

        Args:
            source_dict: Dictionary mapping source codes to descriptions
            vector_db: Initialized vector database instance
        """
        self.source_dict = source_dict
        self.chunker = DocumentChunker(chunk_size=1024, chunk_overlap=200)
        self.vector_db = vector_db


    def extract_text_from_pdf(self, pdf_bytes: bytes, document_id: str) -> List[Dict]:
        """
        Extract text from PDF bytes, page by page.

        Args:
            pdf_bytes: PDF file content as bytes
            document_id: Unique identifier for the document

        Returns:
            List of dicts with page text and page numbers
        """
        pages_data = []

        try:
            with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                total_pages = len(pdf.pages)

                for page_num, page in enumerate(pdf.pages, start=1):
                    text = page.extract_text()

                    if text and text.strip():
                        pages_data.append({
                            "text": text,
                            "page_number": page_num,
                            "total_pages": total_pages
                        })

        except Exception as e:
            print(f"[PDFs] Error extracting text from {document_id}: {e}")

        return pages_data

    def process_pdf(self, s3_key: str, source: str) -> int:
        """
        Process a single PDF: download, extract, chunk, embed, store.

        Args:
            s3_key: S3 key of the PDF file
            source: Source identifier

        Returns:
            Number of chunks added to vector db
        """
        document_id = Path(s3_key).stem
        file_name = Path(s3_key).name

        try:
            # connect to s3
            response = s3.get_object(Bucket=bucket_name, Key=s3_key)
            pdf_bytes = response['Body'].read()

            # get data from pdf
            pages_data = self.extract_text_from_pdf(pdf_bytes, document_id)

            if not pages_data:
                print(f"[PDFs] No text extracted from {document_id}")
                return 0

            all_chunks = []

            publication_date = extract_date_from_filename(file_name)

            # metadata for storage
            base_metadata = {
                "document_id": document_id,
                "source": self.source_dict[source],
                "s3_key": s3_key,
                "file_name": file_name,
                "total_pages": pages_data[0]["total_pages"],
                "publication_date": publication_date if publication_date else "Unknown"
            }

            # text chunk
            for page_data in pages_data:
                chunks = self.chunker.chunk_page(
                    page_text=page_data["text"],
                    page_number=page_data["page_number"],
                    base_metadata=base_metadata
                )
                all_chunks.extend(chunks)

            if not all_chunks:
                return 0

            # Upload chunks to ChromaDB with idempotency
            chunks_added = upload_chunks_to_chroma(all_chunks, s3_key, self.vector_db)

            return chunks_added

        except Exception as e:
            print(f"[PDFs] Error processing {s3_key}: {e}")
            return 0

    def ingest_from_s3(self, s3_prefix: str, source: str, limit: int = None, max_workers: int = 8):
        """
        Ingest PDFs from S3 into vector db.

        Args:
            s3_prefix: S3 prefix to search (e.g., "organized/pdfs/")
            source: Source identifier
            limit: Optional limit on number of PDFs to process
            max_workers: Maximum number of parallel workers (default: 8)
        """
        print(f"[PDFs] Listing PDFs from s3://{bucket_name}/{s3_prefix}...")

        paginator = s3.get_paginator('list_objects_v2')
        pages = paginator.paginate(Bucket=bucket_name, Prefix=s3_prefix)

        # find each object
        pdf_keys = []
        for page in pages:
            if 'Contents' in page:
                for obj in page['Contents']:
                    if obj['Key'].lower().endswith('.pdf'):
                        pdf_keys.append(obj['Key'])

        if limit:
            pdf_keys = pdf_keys[:limit]

        print(f"[PDFs] {len(pdf_keys)} PDFs to process")

        total_chunks = 0
        # process PDFs with threads
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # keep a record of tasks with executor, using s3_key as identifier
            future_to_key = {
                executor.submit(self.process_pdf, s3_key, source): s3_key
                for s3_key in pdf_keys
            }

            # collect results with progress bar
            for future in tqdm(as_completed(future_to_key), total=len(pdf_keys), desc="Processing PDFs"):
                chunks_added = future.result()
                total_chunks += chunks_added

        print(f"\n[PDFs] {'='*50}")
        print(f"[PDFs] Ingestion complete!")
        print(f"[PDFs] {'='*50}")
        print(f"[PDFs] PDFs processed: {len(pdf_keys)}")
        print(f"[PDFs] Total chunks added: {total_chunks}")

        # Get Pinecone index stats
        stats = self.vector_db._index.describe_index_stats()
        total_vectors = stats.get('total_vector_count', 0)
        print(f"[PDFs] Total documents in store: {total_vectors:,}")
