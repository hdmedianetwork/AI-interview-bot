from . import models
from . import schemas
from . import controller
from fastapi import UploadFile,File,Form
from sqlalchemy.orm import Session
from fastapi.security import OAuth2PasswordBearer
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
from src.utils.db import get_db
from fastapi.security import OAuth2PasswordBearer
from fastapi import APIRouter, Depends, HTTPException,status,BackgroundTasks
from loguru import logger as logging
from typing import Optional
import os
from src.utils.jwt import  get_email_from_token
from src.routers.users.models import users as users_model
import urllib
from datetime import datetime
import openai
from threading import Lock

# Global dictionary to store session-related data
session_data_store = {}
session_data_lock = Lock()

# Defining the router
router = APIRouter(
    prefix="/qna",
    tags=["qna"],
    responses={404: {"description": "Not found"}},
)

# Define the upload directory
UPLOAD_DIRECTORY = os.environ['RESUME_UPLOAD_PATH']

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
        

# @router.post("/start-interview/")
# async def start_interview(
#     db: Session = Depends(get_db),
#     token: str = Depends(oauth2_scheme)  # Automatically extract Bearer token
# ):
#     try:
#         # Decode email from the token
#         email = get_email_from_token(token)

#         # Check if user exists
#         user = db.query(users_model.User).filter(users_model.User.email == email).first()
#         if not user:
#             return {
#                 "success": False,
#                 "status": 404,
#                 "isActive": False,
#                 "message": "User not found.",
#                 "data": None,
#             }

#         # Get the latest resume for the user
#         resume_upload = db.query(models.ResumeUpload).filter(models.ResumeUpload.user_id == user.id).order_by(models.ResumeUpload.id.desc()).first()
#         if not resume_upload:
#             return {
#                 "success": False,
#                 "status": 404,
#                 "isActive": False,
#                 "message": "No resume uploaded for this user.",
#                 "data": None,
#             }

#         file_path = resume_upload.file_path
#         if not os.path.exists(file_path):
#             return {
#                 "success": False,
#                 "status": 404,
#                 "isActive": False,
#                 "message": "Resume file not found.",
#                 "data": None,
#             }

#         # Extract text from the file
#         if file_path.endswith(".pdf"):
#             resume_text = controller.extract_text_from_pdf(file_path)
#         elif file_path.endswith(".docx"):
#             resume_text = controller.extract_text_from_docx(file_path)
#         else:
#             return {
#                 "success": False,
#                 "status": 400,
#                 "isActive": False,
#                 "message": "Unsupported file type.",
#                 "data": None,
#             }

#         # Generate the first question
#         question = controller.generate_question(resume_text)

#         # Create a new QnA record in the database
#         qna_entry = models.QnA(
#             user_id=user.id,
#             question_asked=question,
#             generated_answer=None,  # Set as needed
#             answer_review=None      # Set as needed
#         )
#         db.add(qna_entry)
#         db.commit()
#         db.refresh(qna_entry)

#         return {
#             "success": True,
#             "status": 200,
#             "isActive": True,
#             "message": "Interview question generated successfully.",
#             "data": {
#                 "question": question,
#                 "qna_id": qna_entry.id,
#             },
#         }

#     except Exception as e:
#         logging.error(f"Error in start_interview: {e}")
#         return {
#             "success": False,
#             "status": 500,
#             "isActive": False,
#             "message": "An unexpected error occurred. Please try again later.",
#             "data": None,
#         }

# @router.post("/submit-answer/")
# async def submit_answer(
#     request: schemas.SubmitAnswerRequest,  # Use the Pydantic model
#     db: Session = Depends(get_db),
#     token: str = Depends(oauth2_scheme)  # Automatically extract Bearer token
# ):
#     try:
#         # Decode email from the token
#         email = get_email_from_token(token)

#         # Check if user exists
#         user = db.query(users_model.User).filter(users_model.User.email == email).first()
#         if not user:
#             raise HTTPException(
#                 status_code=404,
#                 detail="User not found."
#             )

#         # Fetch the QnA record
#         qna_entry = db.query(models.QnA).filter(models.QnA.id == request.qna_id, models.QnA.user_id == user.id).first()
#         if not qna_entry:
#             raise HTTPException(
#                 status_code=404,
#                 detail="QnA record not found."
#             )

#         # Analyze the given answer and assign a score
#         score = controller.analyze_answer(request.user_answer)  # Replace with your analysis logic

#         # If the score is low, generate a suitable answer
#         generated_answer = None
#         if score < 3:  # Threshold for a poor answer
#             generated_answer = controller.generate_answer(qna_entry.question_asked)

#         # Update the current QnA entry
#         qna_entry.answer_given = request.user_answer
#         qna_entry.answer_review = score
#         qna_entry.generated_answer = generated_answer
#         db.commit()

#         # Generate the next question based on the last response
#         last_response = generated_answer if generated_answer else request.user_answer
#         next_question = controller.generate_question(last_response)

#         # Check if the next question is valid
#         if not next_question:
#             raise HTTPException(
#                 status_code=500,
#                 detail="Failed to generate the next question."
#             )

#         # Create a new QnA entry for the next question
#         next_qna_entry = models.QnA(
#             user_id=user.id,
#             question_asked=next_question,
#             generated_answer=None,
#             answer_review=None,
#         )
#         db.add(next_qna_entry)
#         db.commit()
#         db.refresh(next_qna_entry)

#         return {
#             "success": True,
#             "status": 200,
#             "isActive": True,
#             "message": "Answer submitted successfully and next question generated.",
#             "data": {
#                 "score": score,
#                 "generated_answer": generated_answer,
#                 "next_question": next_question,
#                 "next_qna_id": next_qna_entry.id,
#             },
#         }

#     except HTTPException as http_error:
#         # Return custom HTTPException errors
#         logging.error(f"HTTPException occurred: {http_error.detail}")
#         raise http_error

#     except Exception as e:
#         # Catch unexpected errors
#         logging.error(f"Unexpected error in submit_answer: {e}")
#         raise HTTPException(
#             status_code=500,
#             detail="An unexpected error occurred. Please try again later."
#         )


# Start interview endpoint
@router.post("/start-interview/")
async def start_interview(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
):
    try:
        # Decode email from the token
        email = get_email_from_token(token)
        user = db.query(users_model.User).filter(users_model.User.email == email).first()

        if not user:
            raise HTTPException(status_code=404, detail="User not found.")

        # Check if an active session exists
        active_session = db.query(models.Session).filter_by(user_id=user.id, is_active=True).first()
        if active_session:
            raise HTTPException(status_code=400, detail="An interview session is already active.")

        # Extract resume text
        resume_upload = db.query(models.ResumeUpload).filter(models.ResumeUpload.user_id == user.id).order_by(models.ResumeUpload.id.desc()).first()
        if not resume_upload:
            raise HTTPException(status_code=404, detail="No resume uploaded.")
        
        file_extention = resume_upload.file_format
        if file_extention == "pdf":
            resume_text = controller.extract_text_from_pdf(resume_upload.file_path)
        else:
            resume_text = controller.extract_text_from_docx(resume_upload.file_path)

        # Store resume_text in the global dictionary
        with session_data_lock:
            session_data_store[user.id] = {
                "resume_text": resume_text,
                "session_id": None  # Placeholder for session ID
            }

        # Create a new interview session
        new_session = models.Session(
            user_id=user.id,
            is_active=True,
            start_time=datetime.utcnow()
        )
        db.add(new_session)
        db.commit()
        db.refresh(new_session)

        # Save session ID in the global dictionary
        with session_data_lock:
            session_data_store[user.id]["session_id"] = new_session.id

        # Add the background task to monitor session timeout
        background_tasks.add_task(controller.enforce_session_timeout, new_session.id, db)

        # Generate the first question
        first_question = controller.generate_question(resume_text, new_session.id, db)

        # Record the first QnA entry
        qna_entry = models.QnA(
            user_id=user.id,
            session_id=new_session.id,
            question_asked=first_question,
            generated_answer=None
        )
        db.add(qna_entry)
        db.commit()

        return {
            "success": True,
            "session_id": new_session.id,
            "question": first_question,
            "qna_id": qna_entry.id,
        }
    except Exception as e:
        logging.error(f"Error in start_interview: {e}")
        raise HTTPException(status_code=500, detail="An error occurred.")


# Submit answer endpoint
@router.post("/submit-answer/")
async def submit_answer(
    request: schemas.SubmitAnswerRequest,
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
):
    try:
        # Decode email from the token
        email = get_email_from_token(token)
        user = db.query(users_model.User).filter(users_model.User.email == email).first()

        if not user:
            raise HTTPException(status_code=404, detail="User not found.")

        # Validate active session
        active_session = db.query(models.Session).filter_by(user_id=user.id, is_active=True).first()
        if not active_session:
            raise HTTPException(status_code=400, detail="No active interview session found.")

        # Fetch QnA record
        qna_entry = db.query(models.QnA).filter(models.QnA.id == request.qna_id, models.QnA.user_id == user.id).first()
        if not qna_entry:
            raise HTTPException(status_code=404, detail="QnA record not found.")

        # Retrieve the resume_text from the global dictionary
        with session_data_lock:
            if user.id not in session_data_store:
                raise HTTPException(status_code=400, detail="No resume data found for the session.")
            resume_text = session_data_store[user.id]["resume_text"]

        # Analyze the given answer and assign a score
        score = controller.analyze_answer(request.user_answer)

        # If the score is low, generate a suitable answer
        generated_answer = None
        if score < 3:  # Threshold for a poor answer
            generated_answer = controller.generate_answer(qna_entry.question_asked)

        # Update the current QnA entry
        qna_entry.answer_given = request.user_answer
        qna_entry.answer_review = score
        qna_entry.generated_answer = generated_answer
        db.commit()

        # Generate the next question
        next_question = controller.generate_question(
            resume_text=resume_text,
            session_id=active_session.id,
            db=db,
            previous_answer=request.user_answer
        )

        # Create a new QnA entry for the next question, if valid
        if next_question:
            next_qna = models.QnA(
                user_id=user.id,
                session_id=active_session.id,
                question_asked=next_question
            )
            db.add(next_qna)
            db.commit()
            return {
                "success": True,
                "score": score,
                "next_qna_id": next_qna.id,
                "next_question": next_question,
            }
        else:
            # End session if no more questions
            active_session.is_active = False
            active_session.end_time = datetime.utcnow()
            db.commit()
            return {
                "success": True,
                "score": score,
                "message": "Interview ended as no new questions were generated."
            }
    except Exception as e:
        logging.error(f"Error in submit_answer: {e}")
        raise HTTPException(status_code=500, detail="An error occurred.")


@router.post("/end-interview/")
async def end_interview(
    request: schemas.EndInterviewRequest,
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
):
    try:
        # Decode email from the token
        email = get_email_from_token(token)
        user = db.query(users_model.User).filter(users_model.User.email == email).first()

        if not user:
            raise HTTPException(status_code=404, detail="User not found.")

        # Fetch the session from the database
        session = db.query(models.Session).filter(
            models.Session.id == request.session_id,
            models.Session.user_id == user.id
        ).first()

        if not session:
            raise HTTPException(status_code=404, detail="Session not found.")
        if not session.is_active:
            raise HTTPException(status_code=400, detail="Session is already inactive.")

        # End the session
        session.is_active = False
        session.end_time = datetime.utcnow()
        db.commit()

        return {
            "success": True,
            "message": "Interview session has been ended.",
            "session_id": session.id,
            "end_time": session.end_time
        }
    except Exception as e:
        logging.error(f"Error in end_interview: {e}")
        raise HTTPException(status_code=500, detail="An error occurred while ending the session.")



@router.get("/generate-interview-report/")
async def generate_interview_report(
    request: schemas.EndInterviewRequest,
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
):
    try:
        # Decode email from the token
        email = get_email_from_token(token)
        user = db.query(users_model.User).filter(users_model.User.email == email).first()

        if not user:
            return {
                "success": False,
                "status": 404,
                "message": "User not found.",
                "report": None
            }

        # Fetch the session details
        session = db.query(models.Session).filter(
            models.Session.id == request.session_id,
            models.Session.user_id == user.id
        ).first()

        if not session:
            return {
                "success": False,
                "status": 404,
                "message": "Session not found.",
                "report": None
            }

        # Fetch all QnA records for the session
        qna_records = db.query(models.QnA).filter(
            models.QnA.session_id == session.id
        ).all()

        if not qna_records:
            return {
                "success": False,
                "status": 404,
                "message": "No QnA records found for the session.",
                "report": None
            }

        # Calculate report details
        total_questions = len(qna_records)
        total_score = sum(qna.answer_review for qna in qna_records if qna.answer_review is not None)
        max_possible_score = total_questions * 5  # Assuming a 5-point scale

        # Identify improvement areas
        improvement_areas = [
            {
                "question": qna.question_asked,
                "answer_given": qna.answer_given,
                "suggested_answer": qna.generated_answer
            }
            for qna in qna_records if qna.answer_review is not None and qna.answer_review < 3
        ]

        # Generate study suggestions using OpenAI
        try:
            if improvement_areas:
                study_topics = [area["question"] for area in improvement_areas]
                openai.api_key = os.environ['OPENAI_KEY']
                if not openai.api_key:
                    raise ValueError("Missing OpenAI API key.")

                openai_response = openai.ChatCompletion.create(
                    model="gpt-4o-mini-2024-07-18",
                    messages=[
                        {
                            "role": "system",
                            "content": "You are an expert assistant providing study suggestions."
                        },
                        {
                            "role": "user",
                            "content": f"Provide detailed study suggestions based on the following topics: {study_topics}"
                        }
                    ],
                    max_tokens=150
                )
                suggestions = openai_response.choices[0].message.content.strip()
            else:
                suggestions = "No specific study suggestions needed; all answers were rated sufficiently."
        except Exception as openai_error:
            logging.error(f"OpenAI API Error: {openai_error}")
            suggestions = "Unable to fetch study suggestions due to an internal issue."

        # Compile the report
        report = {
            "Session Details": {
                "Session ID": session.id,
                "User Email": user.email,
                "Start Time": session.start_time.strftime("%Y-%m-%d %H:%M:%S"),
                "End Time": session.end_time.strftime("%Y-%m-%d %H:%M:%S") if session.end_time else "In Progress"
            },
            "Performance Summary": {
                "Total Questions": total_questions,
                "Total Score": total_score,
                "Maximum Possible Score": max_possible_score
            },
            "Areas for Improvement": improvement_areas,
            "Study Suggestions": suggestions
        }

        return {
            "success": True,
            "status": 200,
            "message": "Report generated successfully.",
            "report": report
        }

    except Exception as e:
        logging.error(f"Error in generate_interview_report: {e}")
        return {
            "success": False,
            "status": 500,
            "message": "An error occurred while generating the report.",
            "report": None
        }
