import boto3
import os
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from dotenv import load_dotenv


load_dotenv()

# data types
categories = ['images', 'pdfs', 'videos', 'documents', 'other']

def get_file_type(filename):
    """Categorize file based on file type"""
    extension = Path(filename).suffix.lower()

    image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp'}
    pdf_extensions = {'.pdf'}
    video_extensions = {'.mp4', '.avi', '.mov', '.wmv', '.flv', '.mkv'}
    doc_extensions = {'.doc', '.docx', '.txt', '.rtf', '.odt', '.csv', '.xls', '.xlsx'}

    if extension in image_extensions:
        return 'images'
    elif extension in pdf_extensions:
        return 'pdfs'
    elif extension in video_extensions:
        return 'videos'
    elif extension in doc_extensions:
        return 'documents'
    else:
        return 'other'

def organize_s3_folder(source_prefix, organized_prefix, delete_originals=False, folder_name="folder"):
    """
    Organize S3 files by file type into categorized folders

    Args:
        source_prefix: S3 prefix where source files are located (e.g., "HC/")
        organized_prefix: S3 prefix for organized files (e.g., "HC_organized/")
        delete_originals: Whether to delete original files after copying
        folder_name: Name for logging purposes
    """
    print(f"\n{'='*60}")
    print(f"Organizing: {folder_name}")
    print(f"{'='*60}\n")

    bucket_name = os.getenv("AWS_BUCKET_NAME")
    region = os.getenv("AWS_REGION")
    s3 = boto3.client('s3', region_name=region)

    # Thread-safe counters
    print_lock = Lock()
    stats = {'total_files': 0, 'processed_files': 0, 'by_category': {cat: 0 for cat in categories}}

    def process_file(s3_key):
        """Copy file to organized folder and optionally delete original"""
        try:
            filename = Path(s3_key).name
            category = get_file_type(filename)

            # create new s3 key in organized folder
            new_s3_key = f"{organized_prefix}{category}/{filename}"

            # Copy object to new location
            s3.copy_object(
                Bucket=bucket_name,
                CopySource={'Bucket': bucket_name, 'Key': s3_key},
                Key=new_s3_key
            )

            # Delete original if requested
            if delete_originals:
                s3.delete_object(Bucket=bucket_name, Key=s3_key)

            # Update progress
            with print_lock:
                stats['processed_files'] += 1
                stats['by_category'][category] += 1
                if stats['processed_files'] % 100 == 0:
                    print(f"  Progress: {stats['processed_files']}/{stats['total_files']} files processed")

            return category
        except Exception as e:
            with print_lock:
                print(f"Error processing {s3_key}: {str(e)}")
            return None

    def get_all_files_in_prefix(prefix):
        """Get all files in S3 with given prefix"""
        files = []
        paginator = s3.get_paginator('list_objects_v2')
        pages = paginator.paginate(Bucket=bucket_name, Prefix=prefix)

        for page in pages:
            if 'Contents' in page:
                for obj in page['Contents']:
                    # Skip if it's already in an organized folder
                    if organized_prefix not in obj['Key']:
                        files.append(obj['Key'])

        return files

    print(f"Source: s3://{bucket_name}/{source_prefix}")
    print(f"Destination: s3://{bucket_name}/{organized_prefix}\n")

    # Get all files from source prefix
    files_to_organize = get_all_files_in_prefix(source_prefix)

    stats['total_files'] = len(files_to_organize)
    print(f"Found {stats['total_files']} files to organize\n")

    if stats['total_files'] == 0:
        print("No files to organize.\n")
        return stats

    # Process files in parallel
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(process_file, file_key) for file_key in files_to_organize]

        for future in as_completed(futures):
            future.result()

    # Results summary
    print("\n" + "="*50)
    print(f"Organization Complete: {folder_name}")
    print("="*50)
    print(f"Total files processed: {stats['processed_files']}")
    print(f"\nFiles organized in S3 bucket '{bucket_name}' under {organized_prefix}:")
    for category in categories:
        print(f"  - {organized_prefix}{category}/: {stats['by_category'][category]} files")
    print()

    return stats
