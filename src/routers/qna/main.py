from . import models
from . import schemas
from fastapi import UploadFile,File,Form
from sqlalchemy.orm import Session
from fastapi.security import OAuth2PasswordBearer
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
from src.utils.db import get_db
from fastapi.security import OAuth2PasswordBearer
from fastapi import APIRouter, Depends, HTTPException,status,Request
from loguru import logger as logging
from typing import Optional
import os
from src.utils.jwt import  get_email_from_token
from src.routers.users.models import users as users_model
import urllib

# Defining the router
router = APIRouter(
    prefix="/qna",
    tags=["qna"],
    responses={404: {"description": "Not found"}},
)

# Define the upload directory
UPLOAD_DIRECTORY = r"G:\ReasonableWord\ML_DL project\AI-interview-bot\uploads"
os.makedirs(UPLOAD_DIRECTORY, exist_ok=True)

@router.post("/upload-resume", response_model=schemas.ResumeUploadResponse)
def upload_resume(
    file: UploadFile = File(...),
    user_id: Optional[int] = Form(None),
    token: str = Depends(OAuth2PasswordBearer(tokenUrl="token")),
    db: Session = Depends(get_db),
):
    """
    Upload a resume and store its details in the database.
    """
    try:
        # Decode user information from the token
        email = get_email_from_token(token)
        user = db.query(users_model.User).filter(users_model.User.email == email).first()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        # Validate permissions
        if user.role != "admin" and user_id and user.id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not authorized to upload a resume for another user.",
            )

        # Assign user_id if not provided
        if not user_id:
            user_id = user.id

        # Validate file format
        ALLOWED_FORMATS = ["pdf", "docx", "doc"]
        file_format = file.filename.split(".")[-1].lower()
        if file_format not in ALLOWED_FORMATS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid file format. Allowed formats: {', '.join(ALLOWED_FORMATS)}.",
            )

       # Save the file with a unique path and filename
        email_directory = os.path.join(UPLOAD_DIRECTORY, email)
        os.makedirs(email_directory, exist_ok=True)  # Ensure the directory exists

        file_path = os.path.join(email_directory, file.filename)

        with open(file_path, "wb") as f:
            f.write(file.file.read())

        # URL-safe file path for external use (e.g., API response)
        safe_file_path = urllib.parse.quote(file_path)
        # Create a new resume record
        new_resume = models.ResumeUpload(
            user_id=user_id,
            filename=file.filename,
            file_path=file_path,
            file_format=file_format,
            status=True
        )
        db.add(new_resume)
        db.commit()
        db.refresh(new_resume)

        # Prepare the response
        return schemas.ResumeUploadResponse(
            id=new_resume.id,
            user_id=new_resume.user_id,
            filename=new_resume.filename,
            file_path=new_resume.file_path,
            file_format=new_resume.file_format,
            status=new_resume.status,
            error=new_resume.error,
            created_at=new_resume.created_at,
            updated_at=new_resume.updated_at,
        )

    except HTTPException as e:
        raise e
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred.",
        )
        
        

