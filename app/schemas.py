from pydantic import BaseModel, Field, field_validator
from typing import List, Optional

class GDriveUploadRequest(BaseModel):
    gdriveUrl: str
    userId: str
    email: str
    folderId: Optional[str] = None
    originalFileName: str
    description: Optional[str] = None
    duration: Optional[int] = None
    resolutions: List[str] = []
    segmentDuration: Optional[int] = 10

class VideoMetadataDto(BaseModel):
    id: str
    userId: Optional[str] = Field(None, alias="user_id")
    userEmail: Optional[str] = Field(None, alias="user_email")
    originalFileName: Optional[str] = Field(None, alias="original_file_name")
    description: Optional[str]
    thumbnailUrl: Optional[str] = Field(None, alias="thumbnail_url")
    duration: Optional[int]
    s3Key: Optional[str] = Field(None, alias="s3key")
    status: Optional[str]
    isHidden: bool = Field(..., alias="is_hidden")
    folderId: Optional[str] = Field(None, alias="folder_id")
    resolutions: List[str] = []

    model_config = {
        "from_attributes": True,
        "populate_by_name": True
    }

    @field_validator('resolutions', mode='before')
    @classmethod
    def transform_resolutions(cls, v):
        if isinstance(v, list):
            return [r.resolutions if hasattr(r, 'resolutions') else r for r in v]
        return v
