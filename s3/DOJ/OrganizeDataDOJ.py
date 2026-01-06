import boto3
import os
import zipfile
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from smart_open import open as smart_open
from dotenv import load_dotenv


load_dotenv()

bucket_name = os.getenv("AWS_BUCKET_NAME")
region = os.getenv("AWS_REGION")

s3 = boto3.client('s3', region_name=region)

# data types
categories = ['images', 'pdfs', 'videos', 'documents', 'other']

# thread counter
print_lock = Lock()
stats = {'total_files': 0, 'processed_files': 0}

def get_file_type(filename):
    """Categorize file based on file type"""
    extenstion = Path(filename).suffix.lower()

    image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp'}
    pdf_extensions = {'.pdf'}
    video_extensions = {'.mp4', '.avi', '.mov', '.wmv', '.flv', '.mkv'}
    doc_extensions = {'.doc', '.docx', '.txt', '.rtf', '.odt', '.csv', '.xls', '.xlsx'}

    if extenstion in image_extensions:
        return 'images'
    elif extenstion in pdf_extensions:
        return 'pdfs'
    elif extenstion in video_extensions:
        return 'videos'
    elif extenstion in doc_extensions:
        return 'documents'
    else:
        return 'other'

def process_file(zip_ref, file_path, dataset_num):
    """Extract file from zip and upload directly to S3 in organized folder"""
    try:
        # Skip directories
        if file_path.endswith('/'):
            return None

        category = get_file_type(file_path)
        filename = Path(file_path).name

        # create s3 key
        # TODO ---- please fix this.... god this has caused me so much trouble... why in the world would i not make it consistentso
        s3_key = f"organized/{category}/dataset{dataset_num}_{filename}"

        # Extract file data
        with zip_ref.open(file_path) as source:
            file_data = source.read()

        # Upload directly to S3
        s3.put_object(
            Bucket=bucket_name,
            Key=s3_key,
            Body=file_data
        )

        # Update progress
        with print_lock:
            stats['processed_files'] += 1
            if stats['processed_files'] % 100 == 0:
                print(f"  Progress: {stats['processed_files']}/{stats['total_files']} files processed")

        return category
    except Exception as e:
        with print_lock:
            print(f"Error processing {file_path}: {str(e)}")
        return None



def process_dataset(dataset_num):
    """Stream zip from S3 and organize it"""
    zip_filename = f"DataSet%20{dataset_num}.zip"
    s3_uri = f"s3://{bucket_name}/{zip_filename}"

    with print_lock:
        print(f"\n{s3_uri} starting")

    try:
        # begin stream
        with smart_open(s3_uri, 'rb', transport_params={'client': s3}) as s3_file:
            with zipfile.ZipFile(s3_file) as zip_ref:
                file_list = [f for f in zip_ref.namelist() if not f.endswith('/')]

                # update stats
                with print_lock:
                    print(f"{s3_uri} has {len(file_list)} files")
                    stats['total_files'] += len(file_list)

                # init thread pool for file processing
                with ThreadPoolExecutor(max_workers=5) as executor:
                    futures = [executor.submit(process_file, zip_ref, file_path, dataset_num)
                              for file_path in file_list]

                    for future in as_completed(futures):
                        future.result()

        with print_lock:
            print(f"{s3_uri} Completed")

        # delete when done
        s3.delete_object(Bucket=bucket_name, Key=zip_filename)

        with print_lock:
            print(f"{s3_uri} deleted")

        return dataset_num, len(file_list), None

    except Exception as e:
        with print_lock:
            print(f"[Dataset {dataset_num}] ✗ Error: {str(e)}")
        return dataset_num, 0, str(e)

# Process zip files in parrallel
with ThreadPoolExecutor(max_workers=4) as executor:
    futures = [executor.submit(process_dataset, i) for i in range(1, 9)]

    for future in as_completed(futures):
        print(future.result())

# Results summary
print("\n\n\n")
print("Extraction Complete!")
print(f"\nTotal files processed: {stats['processed_files']}")
print(f"\nFiles organized in S3 bucket '{bucket_name}' under:")
for category in categories:
    print(f"  - organized/{category}/")
