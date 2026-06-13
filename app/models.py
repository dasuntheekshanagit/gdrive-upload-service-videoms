import os
from sqlalchemy import create_engine, Column, String, Boolean, DateTime, ForeignKey, Integer, Table
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import uuid

Base = declarative_base()

class Folder(Base):
    __tablename__ = 'folders'
    __table_args__ = {'extend_existing': True}
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    description = Column(String)

class VideoMetadata(Base):
    __tablename__ = 'video_metadata'
    __table_args__ = {'extend_existing': True}
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String)
    user_email = Column(String)
    original_file_name = Column(String)
    description = Column(String)
    thumbnail_url = Column(String)
    duration = Column(Integer)
    s3key = Column(String)
    status = Column(String) # UPLOADED, PROCESSING, COMPLETED, FAILED, TRANSFERRING_TO_S3
    is_hidden = Column(Boolean, default=True)
    folder_id = Column(String, ForeignKey('folders.id'))
    outputs3key = Column(String)
    encryption_keys3path = Column(String)
    upload_time = Column(DateTime, default=datetime.utcnow)
    processing_completed_time = Column(DateTime)

    folder = relationship("Folder")
    resolutions = relationship("VideoMetadataResolution", back_populates="video_metadata")

class VideoMetadataResolution(Base):
    __tablename__ = 'video_metadata_resolutions'
    __table_args__ = {'extend_existing': True}
    video_metadata_id = Column(String, ForeignKey('video_metadata.id'), primary_key=True)
    resolutions = Column(String, primary_key=True)
    
    video_metadata = relationship("VideoMetadata", back_populates="resolutions")

# Database connection
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:rbZZdeNhhmTzQt1YiMpl@video-ms-db-i-1.c9ka6ysskyi9.eu-north-1.rds.amazonaws.com:5432/video_ms_db")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
