from . import models
from . import schemas
from fastapi import Body
from sqlalchemy.orm import Session
from fastapi.security import OAuth2PasswordBearer
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
from src.utils.jwt import create_access_token, get_email_from_token
from fastapi.security import OAuth2PasswordBearer
from src.database import Database
from fastapi import APIRouter, Depends, HTTPException,status,Request
from sqlalchemy.exc import IntegrityError
from loguru import logger as logging
from src.routers.users.schemas import LoginSchema, TokenResponse

# Dependency to get database session
db_util = Database()

def get_db():
    db = db_util.get_session()
    try:
        yield db
    finally:
        db.close()


# Defining the router
router = APIRouter(
    prefix="/users",
    tags=["Users"],
    responses={404: {"description": "Not found"}},
)

@router.post("/login", response_model=TokenResponse)
def login(user_credentials: LoginSchema = Body(...), db: Session = Depends(get_db)):
    """
    Login endpoint for users to authenticate and obtain a JWT token.
    The password verification is skipped; only the email is checked.
    """
    logging.debug("LOGIN FUNCTION")
    
    # Fetch the user by email
    user = db.query(models.User).filter(models.User.email == user_credentials.email).first()
    logging.error(f"User: {user}")

    # If the user does not exist in the database, return a structured error response
    if not user:
        return {
            "success": False,
            "status": 401,
            "isActive": False,
            "message": "Invalid email or password",
            "data": None  # No user data to include
        }

    # Create the JWT token (skip password verification)
    access_token = create_access_token(data={"sub": user.email})

    # Return the structured success response
    return {
        "success": True,
        "status": 200,
        "isActive": True,
        "message": "User logged in successfully",
        "data": {
            "email_id": user.email,
            "access_token": access_token,
            "token_type": "bearer",
        }
    }



@router.get("/info", response_model=schemas.UserResponse)
def get_user_info(request: Request, db: Session = Depends(get_db)):
    # Get the token from the Authorization header
    token = request.headers.get("Authorization")

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is missing",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Extract the token part
    token = token.split(" ")[1]
    # Get the email from the token
    email = get_email_from_token(token)
    # Fetch the user from the database using the email
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    # Return the response
    return {
        "success": True,
        "status": 200,
        "isActive": True,
        "message": "User found successfully",
        "data": {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "phone_number": user.phone_number,
            "profile_path": user.profile_path,
            "status": user.status,
        },
    }
@router.post("/create", status_code=201)
def create_user(user: schemas.CreateUserSchema, db: Session = Depends(get_db)):
    """
    Endpoint to create a new user.
    """
    try:
        # Check if the user already exists by email or phone number
        existing_user = db.query(models.User).filter(
            (models.User.email == user.email) | (models.User.phone_number == user.phone_number)
        ).first()

        if existing_user:
            return {
                "success": False,
                "status": 400,
                "isActive": False,
                "message": "User with the same email or phone number already exists.",
                "data": None,
            }

        # Create a new User instance
        new_user = models.User(
            name=user.name,
            email=user.email,
            phone_number=user.phone_number,
            role=user.role,
            profile_path=user.profile_path,
            status=user.status
        )

        # Hash and set the password
        new_user.set_password(user.password)

        # Add the new user to the database
        db.add(new_user)
        db.commit()
        db.refresh(new_user)

        # Generate the JWT token for the user
        access_token = create_access_token(data={"sub": new_user.email})

        # Return the structured response
        return {
            "success": True,
            "status": 200,
            "isActive": True,
            "message": "User created successfully",
            "data": {
                "email_id": new_user.email,
                "access_token": access_token,
                "token_type": "bearer",
            }
        }
    except Exception as e:
        db.rollback()
        return {
            "success": False,
            "status": 500,
            "isActive": False,
            "message": f"An unexpected error occurred: {str(e)}",
            "data": None,
        }

@router.put("/update-profile-path", response_model=schemas.UserResponse)
def update_user_profile_path(
    profile_path: str = Body(..., embed=True),  # Only accept `profile_path` in the request body
    token: str = Depends(oauth2_scheme),  # Automatically extracts Bearer token
    db: Session = Depends(get_db),
):
    """
    Update user profile path based on the role.
    Admins can update the profile path for any user,
    while regular users can only update their own profile path.
    """
    # Decode email from the token
    try:
        email = get_email_from_token(token)  # Utility to decode token and get email
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Fetch the user from the database using the decoded email
    user = db.query(models.User).filter(models.User.email == email).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Update profile_path based on the user's role
    if user.role == 'admin' or user.email == email:  # Admins or the user themselves
        user.profile_path = profile_path
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Unauthorized to update profile path",
        )

    # Commit the changes
    try:
        db.commit()
        db.refresh(user)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

    # Return updated user info
    return schemas.UserResponse(
        success=True,
        status=200,
        isActive=user.status == schemas.UserStatus.active,
        message="User profile path updated successfully",
        data=schemas.UserData(
            id=user.id,
            name=user.name,  # Ensure this field is not None
            email=user.email,
            phone_number=user.phone_number or "",  # Ensure a default value if None
            profile_path=user.profile_path,
            status=user.status,
        ),
    )


@router.put("/update-user-info", response_model=schemas.UserResponse)
def update_user_info(
    updated_info: schemas.UserResponseData = Body(...),  # Optional fields for update
    token: str = Depends(oauth2_scheme),  # Automatically extracts Bearer token
    db: Session = Depends(get_db),
):
    """
    Update user information.
    Admins can update all fields.
    Regular users can update their name, phone number, and profile path.
    """
    # Decode email from the token
    try:
        email = get_email_from_token(token)  # Utility to decode token and get email
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Fetch the user from the database using the decoded email
    user = db.query(models.User).filter(models.User.email == email).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Update fields dynamically based on the request body
    for field, value in updated_info.dict(exclude_unset=True).items():
        if field in ["name", "phone_number", "profile_path"] or user.role == "admin":
            setattr(user, field, value)  # Dynamically update the attribute

    # Commit the changes
    try:
        db.commit()
        db.refresh(user)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

    # Return updated user info
    return {
        "success": True,
        "status": 200,
        "isActive": user.status == 'active',  # Assuming 'active' means the user is active
        "message": "User information updated successfully",
        "data": {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "phone_number": user.phone_number,
            "role": user.role,
            "profile_path": user.profile_path,
            "status": user.status,
        },
    }
