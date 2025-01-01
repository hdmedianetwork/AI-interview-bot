from src.utils.db import get_db
from sqlalchemy.orm import Session
from loguru import logger as logging
from src.utils.jwt import  get_email_from_token
from fastapi.security import OAuth2PasswordBearer
from src.routers.qna.models import qna as qna_models
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
from fastapi import APIRouter, Depends, HTTPException
from src.routers.users.models import users as users_model


# Defining the router
router = APIRouter(
    prefix="/dashboard",
    tags=["dashboard"],
    responses={404: {"description": "Not found"}},
)


@router.get("/get-user-qna/")
async def get_user_qna(
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
):
    try:
        # Decode email from the token
        email = get_email_from_token(token)
        user = db.query(users_model.User).filter(users_model.User.email == email).first()

        if not user:
            raise HTTPException(status_code=404, detail="User not found.")

         # Fetch all QnA records for the user, sorted by id (question_id) in descending order
        qna_records = (
            db.query(qna_models.QnA)
            .filter(qna_models.QnA.user_id == user.id)
            .order_by(qna_models.QnA.id.desc())  # Replace `id` with `question_id` if applicable
            .all()
        )

        if not qna_records:
            return {
                "success": False,
                "status": 200,
                "message": "No QnA records found for the user.",
                "qna_list": []
            }

        # Format the data into a list of dictionaries
        qna_list = [
            {
                "qna_id": qna.id,
                "session_id": qna.session_id,
                "question_asked": qna.question_asked,
                "answer_given": qna.answer_given,
                "score": qna.answer_review,
                "created_at": qna.created_at.isoformat() if qna.created_at else None,
                "updated_at": qna.updated_at.isoformat() if qna.updated_at else None
            }
            for qna in qna_records
        ]

        return {
            "success": True,
            "status": 200,
            "message": "QnA records retrieved successfully.",
            "qna_list": qna_list
        }
    except Exception as e:
        logging.error(f"Error in get_user_qna: {e}")
        raise HTTPException(status_code=500, detail="An error occurred while retrieving QnA records.")