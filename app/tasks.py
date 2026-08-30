import re
import subprocess
import json
import boto3
import os
from sqlalchemy.orm import Session
from .models import VideoMetadata, VideoMetadataResolution, Folder, SessionLocal
from .schemas import GDriveUploadRequest
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# AWS Configuration
AWS_REGION = os.getenv("AWS_REGION", "eu-north-1")
S3_INPUT_BUCKET = os.getenv("S3_INPUT_BUCKET", "videoms-input-bucket")
SQS_QUEUE_URL = os.getenv("SQS_QUEUE_URL", "https://sqs.eu-north-1.amazonaws.com/637423445599/video-ms-convert.fifo")
EC2_INSTANCE_ID = os.getenv("EC2_INSTANCE_ID", "i-03a1d1cb5ad9dece8")

import requests

# YouTube Upload Service Configuration
YOUTUBE_UPLOAD_SERVICE_URL = os.getenv("YOUTUBE_UPLOAD_SERVICE_URL", "http://localhost:8002")

sqs_client = boto3.client('sqs', region_name=AWS_REGION)
ec2_client = boto3.client('ec2', region_name=AWS_REGION)

def extract_gdrive_id(url: str) -> str:
    # Matches file/d/<ID>/ or id=<ID>
    match = re.search(r'(?:/d/|id=)([\w-]+)', url)
    if match:
        return match.group(1)
    return url # Return as is if already an ID

def run_rclone_transfer(gdrive_id: str, s3_key: str):
    # rclone backend copyid gdrive: <id> s3:<bucket>/<key>
    # Note: Requires rclone.conf to be configured
    command = [
        "rclone", "backend", "copyid", 
        "gdrive:", gdrive_id, 
        f"s3:{S3_INPUT_BUCKET}/{s3_key}"
    ]
    logger.info(f"Running rclone command: {' '.join(command)}")
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(f"Rclone failed: {result.stderr}")
    logger.info("Rclone transfer completed successfully")

def process_gdrive_upload(video_id: str, request_data: dict):
    db: Session = SessionLocal()
    video = None
    try:
        video = db.query(VideoMetadata).filter(VideoMetadata.id == video_id).first()
        if not video:
            logger.error(f"Video {video_id} not found in DB")
            return

        # 1. Extract ID and Determine S3 Key
        gdrive_id = extract_gdrive_id(request_data['gdriveUrl'])
        
        folder_path = ""
        if video.folder_id:
            folder = db.query(Folder).filter(Folder.id == video.folder_id).first()
            if folder:
                folder_path = folder.name

        s3_key = f"raw/{(folder_path + '/') if folder_path else ''}{video.original_file_name}"
        video.s3key = s3_key
        db.commit()

        # 2. Run Rclone
        run_rclone_transfer(gdrive_id, s3_key)

        # 3. Check upload destination
        upload_to_youtube = request_data.get('uploadToYouTube', False)

        if upload_to_youtube:
            video.status = "QUEUED_FOR_YOUTUBE"
            db.commit()
            
            yt_url = f"{YOUTUBE_UPLOAD_SERVICE_URL}/api/youtube-upload/process/{video.id}"
            payload = {
                "videoId": video.id,
                "title": video.original_file_name,
                "description": video.description,
                "privacyStatus": "private"
            }
            logger.info(f"Triggering YouTube Upload Service at {yt_url} for video {video_id}")
            try:
                resp = requests.post(yt_url, json=payload, timeout=10)
                logger.info(f"YouTube Upload Service response: {resp.status_code} - {resp.text}")
            except Exception as yt_err:
                logger.error(f"Failed to trigger YouTube service: {yt_err}")
        else:
            # 4. Standard FFmpeg conversion path: Update Status & Send SQS Message
            video.status = "UPLOADED"
            db.commit()

            message_body = {
                "videoId": video.id,
                "s3Key": s3_key,
                "bucket": S3_INPUT_BUCKET,
                "folderPath": folder_path,
                "fileName": video.original_file_name,
                "resolutions": ",".join([r.resolutions for r in video.resolutions]),
                "segmentDuration": request_data.get('segmentDuration', 10)
            }
            
            sqs_params = {
                'QueueUrl': SQS_QUEUE_URL,
                'MessageBody': json.dumps(message_body)
            }
            
            if SQS_QUEUE_URL.endswith(".fifo"):
                sqs_params['MessageGroupId'] = video.id
                sqs_params['MessageDeduplicationId'] = video.id
                
            sqs_client.send_message(**sqs_params)
            logger.info(f"SQS message sent for video {video_id}")

            # 5. Start EC2 Instance
            logger.info(f"Starting EC2 instance {EC2_INSTANCE_ID}")
            ec2_client.start_instances(InstanceIds=[EC2_INSTANCE_ID])

    except Exception as e:
        logger.error(f"Error processing upload for {video_id}: {str(e)}")
        if video:
            video.status = "FAILED"
            db.commit()
    finally:
        db.close()
