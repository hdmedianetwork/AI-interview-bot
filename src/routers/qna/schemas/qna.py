from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class ResumeUploadBase(BaseModel):
    id: Optional[int]
    user_id: Optional[int]  # Optional because admin might upload without linking to a user
    filename: str
    file_path: str
    file_format: str
    status: Optional[str] = "uploaded"
    error: Optional[str] = None


class ResumeUploadCreate(ResumeUploadBase):
    pass


class ResumeUploadUpdate(BaseModel):
    filename: Optional[str]
    file_path: Optional[str]
    file_format: Optional[str]
    status: Optional[str]
    error: Optional[str]


class ResumeUploadResponse(BaseModel):
    id: int
    user_id: int
    filename: str
    file_path: str
    file_format: str
    status: str
    error: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True  # Allows Pydantic to work with ORM models
