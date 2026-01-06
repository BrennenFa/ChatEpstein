import argparse
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from ingest_pdfs import PDFIngestionPipeline
from ingest_images import ImageIngestionPipeline
from ingest_text import TextIngestionPipeline
from pinecone_connect import pinecone_connect

# Disable tokenizers parallelism warning when using multiprocessing
os.environ["TOKENIZERS_PARALLELISM"] = "false"

# Centralized source dictionary
SOURCE_DICT = {
    "DOJ": "DOJ Disclosures, Including Disclosures Under the Epstein Files Transparency Act (H.R. 4405)",
    "HC": "House Committee on Oversight and Reform Depositions and Testimonies",
    "EE": "Oversight Committee Releases Additional Epstein Estate Documents"
}

def ingest_pdfs(s3_prefix: str, source: str, limit: int = None, vector_db = None, max_workers: int = 8):
    """Run PDF ingestion pipeline"""
    print(f"\n{'='*60}")
    print(f"[PDFs] Starting PDF Ingestion (workers: {max_workers})")
    print(f"{'='*60}")
    pipeline = PDFIngestionPipeline(source_dict=SOURCE_DICT, vector_db=vector_db)
    pipeline.ingest_from_s3(s3_prefix, source, limit, max_workers=max_workers)

def ingest_images(s3_prefix: str, source: str, limit: int = None, vector_db = None, max_workers: int = 4):
    """Run Image ingestion pipeline"""
    print(f"\n{'='*60}")
    print(f"[Images] Starting Image Ingestion (OCR) (workers: {max_workers})")
    print(f"{'='*60}")
    pipeline = ImageIngestionPipeline(source_dict=SOURCE_DICT, vector_db=vector_db)
    pipeline.ingest_from_s3(s3_prefix, source, limit, max_workers=max_workers)

def ingest_text(s3_prefix: str, source: str, limit: int = None, vector_db = None, max_workers: int = 4):
    """Run Text ingestion pipeline"""
    print(f"\n{'='*60}")
    print(f"[Text] Starting Text Ingestion (workers: {max_workers})")
    print(f"{'='*60}")
    pipeline = TextIngestionPipeline(source_dict=SOURCE_DICT, vector_db=vector_db)
    pipeline.ingest_from_s3(s3_prefix, source, limit, max_workers=max_workers)

def main():
    parser = argparse.ArgumentParser(
        description="Ingest documents (PDFs, Images, and Text) into vector database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run all ingestion types (default)
  python start_pipeline.py

  # Run only PDF ingestion
  python start_pipeline.py --type pdfs

  # Run only image ingestion
  python start_pipeline.py --type images

  # Run only text ingestion
  python start_pipeline.py --type text

  # Limit processing to first 10 documents
  python start_pipeline.py --type pdfs --limit 10

  # Custom S3 prefix and source
  python start_pipeline.py --type pdfs --prefix "organized/pdfs/" --source DOJ

  # Specify number of parallel workers
  python start_pipeline.py --type pdfs --prefix "organized/pdfs/" --source DOJ --workers 16
        """
    )

    parser.add_argument(
        '--type',
        choices=['pdfs', 'images', 'text'],
        help='Type of documents to ingest'
    )

    parser.add_argument(
        '--prefix',
        type=str,
        help='S3 prefix to search for documents'
    )

    parser.add_argument(
        '--source',
        help='Source identifier for the documents'
    )

    parser.add_argument(
        '--limit',
        type=int,
        help='Limit the number of documents to process'
    )

    parser.add_argument(
        '--workers',
        type=int,
        help='Number of parallel workers for processing (default: 8 for PDFs, 4 for images/text)'
    )

    args = parser.parse_args()

    # Determine what to run
    run_pdfs = args.type == 'pdfs'
    run_images = args.type == 'images'
    run_text = args.type == 'text'

    # handle no type
    if args.type is None:
        print("no type")
        return False
    # handle no prefix
    if args.prefix is None:
        print("no prefix")
        return False
    # Run sequentially if only one type is selected
    print("Initializing vector database...")
    vector_db = pinecone_connect()

    if run_pdfs:
        pdf_prefix = args.prefix
        pdf_source = args.source
        pdf_workers = args.workers
        ingest_pdfs(s3_prefix=pdf_prefix, source=pdf_source, limit=args.limit, vector_db=vector_db, max_workers=pdf_workers)

    if run_images:
        image_prefix = args.prefix
        image_source = args.source
        image_workers = args.workers
        ingest_images(s3_prefix=image_prefix, source=image_source, limit=args.limit, vector_db=vector_db, max_workers=image_workers)

    if run_text:
        text_prefix = args.prefix
        text_source = args.source
        text_workers = args.workers
        ingest_text(s3_prefix=text_prefix, source=text_source, limit=args.limit, vector_db=vector_db, max_workers=text_workers)

    print(f"\n{'='*60}")
    print("All ingestion tasks completed!")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    main()
