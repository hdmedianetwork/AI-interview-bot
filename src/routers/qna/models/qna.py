from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    ForeignKey,
    TIMESTAMP,
    func,
    CheckConstraint,
    DateTime,
    Boolean
)
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
Base = declarative_base()
from datetime import datetime


class ResumeUpload(Base):
    __tablename__ = "resume_upload"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer)
    filename = Column(String(255), nullable=False)
    file_path = Column(String(255), nullable=False)
    file_format = Column(String(50), nullable=False)
    status = Column(String(20))
    error = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())


class QnA(Base):
    __tablename__ = "qna"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer)
    session_id = Column(Integer)
    question_asked = Column(Text, nullable=False)
    answer_given = Column(Text, nullable=True)
    answer_review = Column(Integer, CheckConstraint("answer_review >= 1 AND answer_review <= 5"), nullable=True)
    generated_answer = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())


class Session(Base):
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer)
    is_active = Column(Boolean, default=True)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=True)
    
    
"""
CREATE TABLE sessions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);


"""