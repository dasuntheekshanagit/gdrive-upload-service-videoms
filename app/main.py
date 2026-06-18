from fastapi import FastAPI, BackgroundTasks, Depends, HTTPException, File, UploadFile, Form
from sqlalchemy.orm import Session
import uuid
from datetime import datetime
from typing import Optional
import json
import os
import boto3

from .models import VideoMetadata, VideoMetadataResolution, SessionLocal, engine, Base
from .schemas import GDriveUploadRequest, VideoMetadataDto
from .tasks import process_gdrive_upload

from fastapi.middleware.cors import CORSMiddleware

# Create tables if they don't exist (though they should exist from Spring Boot)
Base.metadata.create_all(bind=engine)

app = FastAPI(title="GDrive Upload Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.post("/api/gdrive-upload", response_model=VideoMetadataDto)
def upload_from_gdrive(
    background_tasks: BackgroundTasks,
    request: str = Form(...),
    thumbnail: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    # Parse request JSON string
    try:
        request_data = json.loads(request)
        req = GDriveUploadRequest(**request_data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid request payload: {str(e)}")

    video_id = str(uuid.uuid4())
    
    # Upload thumbnail to S3 if provided
    thumbnail_url_path = None
    if thumbnail:
        try:
            AWS_REGION = os.getenv("AWS_REGION", "eu-north-1")
            S3_OUTPUT_BUCKET = os.getenv("S3_OUTPUT_BUCKET", "videoms-output-bucket")
            s3_client = boto3.client('s3', region_name=AWS_REGION)
            
            # Clean filename and build key: thumbnails/video/{video_id}_{filename}
            clean_filename = "".join([c for c in thumbnail.filename if c.isalnum() or c in ['.', '_', '-']]).strip()
            thumbnail_key = f"thumbnails/video/{video_id}_{clean_filename}"
            
            s3_client.upload_fileobj(
                thumbnail.file,
                S3_OUTPUT_BUCKET,
                thumbnail_key,
                ExtraArgs={"ContentType": thumbnail.content_type or "image/jpeg"}
            )
            thumbnail_url_path = thumbnail_key
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to upload thumbnail: {str(e)}")

    # 1. Create VideoMetadata record
    video = VideoMetadata(
        id=video_id,
        user_id=req.userId,
        user_email=req.email,
        original_file_name=req.originalFileName,
        description=req.description,
        duration=req.duration,
        status="TRANSFERRING_TO_S3",
        folder_id=req.folderId,
        is_hidden=True,
        thumbnail_url=thumbnail_url_path,
        upload_time=datetime.utcnow()
    )
    db.add(video)
    
    # 2. Add resolutions
    for res in req.resolutions:
        resolution = VideoMetadataResolution(video_metadata_id=video_id, resolutions=res)
        db.add(resolution)
    
    db.commit()
    db.refresh(video)

    # 3. Trigger Background Task
    background_tasks.add_task(process_gdrive_upload, video_id, req.dict())

    return video

@app.get("/health")
def health_check():
    return {"status": "healthy"}
