import requests
import boto3
from io import BytesIO
import os
from dotenv import load_dotenv

load_dotenv()

bucket_name = os.getenv("AWS_BUCKET_NAME")
region = os.getenv("AWS_REGION")

#connect to s3
s3 = boto3.client('s3', region_name=region)

print("Connected to S3!!!!")

# upload files
for i in range(1, 9):

	url = f"https://www.justice.gov/epstein/files/DataSet%20{i}.zip"
	filename = url.split('/')[-1]
	print(f"Uploading {filename} to S3 bucket {bucket_name}...")
	
	with requests.get(url, stream=True) as r:
		r.raise_for_status()
		s3.upload_fileobj(r.raw, bucket_name, filename)

