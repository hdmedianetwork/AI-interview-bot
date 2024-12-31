from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    ForeignKey,
    TIMESTAMP,
    func,
)
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
Base = declarative_base()


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
    updated_at = Column(
        TIMESTAMP, server_default=func.now(), onupdate=func.now()
    )
