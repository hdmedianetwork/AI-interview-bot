from sqlalchemy import Column, Integer, String, DateTime, Enum, TIMESTAMP
from sqlalchemy.orm import validates
from sqlalchemy.sql import func
from sqlalchemy.ext.declarative import declarative_base
import enum
import re
import bcrypt

Base = declarative_base()

class UserRole(enum.Enum):
    admin = "admin"
    user = "user"

class UserStatus(enum.Enum):
    active = "active"
    inactive = "inactive"

class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    phone_number = Column(String(15), unique=True)
    password = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), nullable=False)
    profile_path = Column(String(255), default="default.jpg")
    status = Column(Enum(UserStatus), default=UserStatus.active)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp())


    @validates('email')
    def validate_email(self, key, email):
        if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            raise ValueError("Invalid email address")
        return email

    @validates('phone_number')
    def validate_phone_number(self, key, phone_number):
        if phone_number and not re.match(r"^\+?[1-9]\d{1,14}$", phone_number):
            raise ValueError("Invalid phone number")
        return phone_number

    def set_password(self, raw_password: str):
        """Hashes and sets the user's password."""
        self.password = bcrypt.hashpw(raw_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    def verify_password(self, raw_password: str) -> bool:
        """Verifies the provided password against the stored hash."""
        return bcrypt.checkpw(raw_password.encode('utf-8'), self.password.encode('utf-8'))

    def __repr__(self):
        return f"<User(id={self.id}, name={self.name}, email={self.email}, role={self.role})>"
