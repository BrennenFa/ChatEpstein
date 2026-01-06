import boto3
import os
from pathlib import Path
from dotenv import load_dotenv
import threading
import time
from queue import Queue
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import pickle

load_dotenv()

SCOPES = ['https://www.googleapis.com/auth/drive.readonly']

def connect_to_drive(credentials_file, token_file):
    """Connect to google drive"""
    creds = None

    if token_file.exists():
        with open(token_file, 'rb') as token:
            creds = pickle.load(token)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                str(credentials_file), SCOPES)
            creds = flow.run_local_server(port=8080)

        with open(token_file, 'wb') as token:
            pickle.dump(creds, token)

    return build('drive', 'v3', credentials=creds)

def list_files_in_folder(service, folder_id):
    """List all files in a Google Drive folder recursively - yields files instead of building list"""
    page_token = None

    while True:
        query = f"'{folder_id}' in parents"
        results = service.files().list(
            q=query,
            pageSize=1000,
            fields="nextPageToken, files(id, name, mimeType, parents)",
            pageToken=page_token
        ).execute()

        items = results.get('files', [])

        for item in items:
            if item['mimeType'] == 'application/vnd.google-apps.folder':
                # Recursively yield files from subfolders
                yield from list_files_in_folder(service, item['id'])
            else:
                yield item

        page_token = results.get('nextPageToken')
        if not page_token:
            break

def download_file(service, file_id, file_name, destination):
    """Download a file from Google Drive - streams directly to disk"""
    try:
        request = service.files().get_media(fileId=file_id)

        # Stream directly to file instead of buffering in memory
        with open(destination, 'wb') as f:
            downloader = MediaIoBaseDownload(f, request)
            done = False
            while not done:
                status, done = downloader.next_chunk()

        return True
    except Exception as e:
        print(f"Error downloading {file_name}: {e}")
        return False

def download_worker(service, files_iterator, uploaded, total_files, local_download_dir, upload_queue, download_complete, stats, stats_lock):
    """Download files from Google Drive in batches"""
    batch_size = 50
    batch = []
    batch_num = 0

    for file in files_iterator:
        if file['name'] in uploaded:
            continue

        batch.append(file)

        if len(batch) >= batch_size:
            batch_num += 1
            print(f"\n[DOWNLOAD] Batch {batch_num}: Downloading {len(batch)} files...")

            downloaded_files = []
            for f in batch:
                file_path = local_download_dir / f['name']
                if download_file(service, f['id'], f['name'], file_path):
                    downloaded_files.append(file_path)

                    with stats_lock:
                        stats['downloaded'] += 1

                        if stats['downloaded'] % 10 == 0:
                            print(f"[DOWNLOAD] Downloaded {stats['downloaded']}/{total_files} files")
                else:
                    with stats_lock:
                        stats['errors'] += 1

            if downloaded_files:
                upload_queue.put(downloaded_files)

            batch = []
            time.sleep(1)

    # Process remaining files in final batch
    if batch:
        batch_num += 1
        print(f"\n[DOWNLOAD] Batch {batch_num}: Downloading {len(batch)} files...")

        downloaded_files = []
        for f in batch:
            file_path = local_download_dir / f['name']
            if download_file(service, f['id'], f['name'], file_path):
                downloaded_files.append(file_path)

                with stats_lock:
                    stats['downloaded'] += 1
            else:
                with stats_lock:
                    stats['errors'] += 1

        if downloaded_files:
            upload_queue.put(downloaded_files)

    download_complete.set()
    print("\n[DOWNLOAD] Thread finished")

def upload_worker(s3, bucket_name, s3_prefix, upload_queue, download_complete, stats, stats_lock):
    """Upload files to S3 and delete locally"""
    while True:
        if download_complete.is_set() and upload_queue.empty():
            break

        try:
            files = upload_queue.get(timeout=5)
        except:
            continue

        print(f"\n[UPLOAD] Processing {len(files)} files...")

        for file_path in files:
            try:
                s3_key = f"{s3_prefix}{file_path.name}"

                s3.upload_file(str(file_path), bucket_name, s3_key)

                file_path.unlink()

                with stats_lock:
                    stats['uploaded'] += 1

                    if stats['uploaded'] % 10 == 0:
                        print(f"[UPLOAD] Uploaded {stats['uploaded']} files")

            except Exception as e:
                print(f"[UPLOAD] Error with {file_path}: {e}")
                with stats_lock:
                    stats['errors'] += 1

        upload_queue.task_done()

    print(f"\n[UPLOAD] Thread finished")


def upload_drive_folder_to_s3(folder_id, s3_prefix, folder_name="folder"):
    """
    Download files from a Google Drive folder and upload them to S3

    Args:
        folder_id: Google Drive folder ID
        s3_prefix: S3 prefix/path where files will be uploaded (e.g., "HC/")
        folder_name: Name for logging purposes
    """
    print(f"\n{'='*60}")
    print(f"Processing: {folder_name}")
    print(f"{'='*60}\n")

    # Connect to S3
    bucket_name = os.getenv("AWS_BUCKET_NAME")
    region = os.getenv("AWS_REGION")
    s3 = boto3.client('s3', region_name=region)

    # Get paths
    script_dir = Path(__file__).parent
    project_root = script_dir.parent.parent
    local_download_dir = Path(project_root / "data")
    credentials_file = project_root / "keys" / "google_secret.json"
    token_file = project_root / "keys" / "token.pickle"

    os.makedirs(local_download_dir, exist_ok=True)

    # Threading setup
    upload_queue = Queue()
    download_complete = threading.Event()
    stats = {'downloaded': 0, 'uploaded': 0, 'errors': 0}
    stats_lock = threading.Lock()

    # Connect to Google Drive
    drive_service = connect_to_drive(credentials_file, token_file)

    # Find already uploaded files to ensure idempotency
    uploaded = set()
    paginator = s3.get_paginator('list_objects_v2')
    pages = paginator.paginate(Bucket=bucket_name, Prefix=s3_prefix)

    for page in pages:
        if 'Contents' in page:
            for obj in page['Contents']:
                filename = obj['Key'].replace(s3_prefix, '')
                uploaded.add(filename)

    print(f"Found {len(uploaded)} already uploaded files")
    print(f"Files will be uploaded to s3://{bucket_name}/{s3_prefix}\n")

    # Count total files
    total_files = sum(1 for _ in list_files_in_folder(drive_service, folder_id))
    print(f"Found {total_files} total files to process\n")

    # Get iterator for downloading files
    files_iterator = list_files_in_folder(drive_service, folder_id)

    # Start threads
    download_thread = threading.Thread(
        target=download_worker,
        args=(drive_service, files_iterator, uploaded, total_files, local_download_dir, upload_queue, download_complete, stats, stats_lock)
    )
    upload_thread = threading.Thread(
        target=upload_worker,
        args=(s3, bucket_name, s3_prefix, upload_queue, download_complete, stats, stats_lock)
    )

    download_thread.start()
    upload_thread.start()

    # Wait for threads to complete
    download_thread.join()
    upload_thread.join()

    print("\n" + "="*50)
    print(f"Complete: {folder_name}")
    print("="*50)
    print(f"Downloaded: {stats['downloaded']}")
    print(f"Uploaded: {stats['uploaded']}")
    print(f"Errors: {stats['errors']}")

    print("\nCleaning up...")
    if local_download_dir.exists():
        import shutil
        shutil.rmtree(local_download_dir)

    print("Done!\n")

    return stats
