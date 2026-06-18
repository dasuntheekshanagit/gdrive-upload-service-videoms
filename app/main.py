from fastapi import FastAPI, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session
import uuid
from datetime import datetime

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
    request: GDriveUploadRequest, 
    background_tasks: BackgroundTasks, 
    db: Session = Depends(get_db)
):
    # 1. Create VideoMetadata record
    video_id = str(uuid.uuid4())
    video = VideoMetadata(
        id=video_id,
        user_id=request.userId,
        user_email=request.email,
        original_file_name=request.originalFileName,
        description=request.description,
        duration=request.duration,
        status="TRANSFERRING_TO_S3",
        folder_id=request.folderId,
        is_hidden=True,
        upload_time=datetime.utcnow()
    )
    db.add(video)
    
    # 2. Add resolutions
    for res in request.resolutions:
        resolution = VideoMetadataResolution(video_metadata_id=video_id, resolutions=res)
        db.add(resolution)
    
    db.commit()
    db.refresh(video)

    # 3. Trigger Background Task
    background_tasks.add_task(process_gdrive_upload, video_id, request.dict())

    return video

@app.get("/health")
def health_check():
    return {"status": "healthy"}
