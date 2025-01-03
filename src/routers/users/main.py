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
import bcrypt
import jwt


# Dependency to get database session
db_util = Database()

def get_db():
    db = db_util.get_session()
    try:
        yield db
    finally:
        db.close()

def verify_password(raw_password: str,password:str) -> bool:
        """Verifies the provided password against the stored hash."""
        return bcrypt.checkpw(raw_password.encode('utf-8'), password.encode('utf-8'))

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
    """
    logging.debug("Login function called")

    try:
        # Log the email for debugging (avoid logging plaintext passwords in production)
        logging.info(f"Login attempt for email: {user_credentials.email}")

        # Fetch the user by email
        user = db.query(models.User.id, models.User.email, models.User.password).filter(
            models.User.email == user_credentials.email
        ).first()

        # Log the query result for debugging
        if user:
            logging.debug(f"User found: {user.email}")
        else:
            logging.warning(f"Login failed: User with email {user_credentials.email} not found")

        # If the user does not exist in the database
        if not user:
            return {
                "success": False,
                "status": 401,
                "isActive": False,
                "message": "The email you entered does not match any account. Please check and try again.",
                "data": None  # No user data to include
            }

        # Verify the provided password against the stored hashed password
        if not verify_password(user_credentials.password, user.password):
            logging.warning(f"Login failed: Incorrect password for email {user_credentials.email}")
            return {
                "success": False,
                "status": 401,
                "isActive": False,
                "message": "The password you entered is incorrect. Please try again.",
                "data": None
            }

        # Create the JWT token
        access_token = create_access_token(data={"sub": user.email})

        # Return the structured success response
        logging.info(f"User {user.email} logged in successfully")
        return {
            "success": True,
            "status": 200,
            "isActive": True,
            "message": "Login successful. Welcome back!",
            "data": {
                "email_id": user.email,
                "access_token": access_token,
                "token_type": "bearer",
            }
        }

    except Exception as e:
        # Handle unexpected errors
        logging.error(f"An error occurred during login: {e}")
        return {
            "success": False,
            "status": 500,
            "isActive": False,
            "message": "An unexpected error occurred. Please try again later.",
            "data": None
        }


@router.get("/info", response_model=schemas.UserResponse)
def get_user_info(request: Request, db: Session = Depends(get_db)):
    """
    Endpoint to fetch user information using the JWT token.
    """
    try:
        # Get the token from the Authorization header
        token = request.headers.get("Authorization")

        # Check if the token is missing
        if not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token is missing",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Ensure the token follows the "Bearer <token>" format
        if not token.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid token format. Token must start with 'Bearer'.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Extract the actual token part
        token = token.split(" ")[1]

        # Get the email from the token
        email = get_email_from_token(token)

        # Fetch the user from the database using the email
        user = db.query(models.User).filter(models.User.email == email).first()

        # Check if the user exists in the database
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found. Please ensure the token is valid.",
            )

        # Check if the user account is active
        if not user.status:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your account is inactive. Please contact support.",
            )

        # Log the user's role
        logging.info(f"User role for {user.email}: {user.role}")

        # Return the structured response with the user's role included
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
                "role": user.role,  # Convert Enum (if applicable) to its value
                "status": user.status,
            },
        }

    except HTTPException as http_exc:
        raise http_exc

    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred. Please try again later.",
        )


    
@router.post("/create", status_code=201)
def create_user(user: schemas.CreateUserSchema, db: Session = Depends(get_db)):
    """
    Endpoint to create a new user.
    """
    try:
        # Log the user creation attempt
        logging.info(f"User creation attempt for email: {user.email}, phone: {user.phone_number}")

        # Check if a user with the same email already exists
        email_exists = db.query(models.User).filter(models.User.email == user.email).first()
        if email_exists:
            logging.warning(f"User creation failed: Email {user.email} already exists")
            return {
                "success": False,
                "status": 400,
                "isActive": False,
                "message": "A user with this email address already exists. Please use a different email.",
                "data": None,
            }

        # Check if a user with the same phone number already exists
        phone_exists = db.query(models.User).filter(models.User.phone_number == user.phone_number).first()
        if phone_exists:
            logging.warning(f"User creation failed: Phone number {user.phone_number} already exists")
            return {
                "success": False,
                "status": 400,
                "isActive": False,
                "message": "A user with this phone number already exists. Please use a different phone number.",
                "data": None,
            }

        # Ensure all required fields are provided
        if not user.name or not user.email or not user.phone_number or not user.password:
            logging.warning(f"User creation failed: Missing required fields for email {user.email}")
            return {
                "success": False,
                "status": 422,
                "isActive": False,
                "message": "Missing required fields. Ensure that name, email, phone number, and password are provided.",
                "data": None,
            }

        # Create a new User instance (role set to "user" by default)
        new_user = models.User(
            name=user.name,
            email=user.email,
            phone_number=user.phone_number,
            role="user",  # Default role
            profile_path=user.profile_path,
            status=user.status,
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
        logging.info(f"User {new_user.email} created successfully with role 'user'")
        return {
            "success": True,
            "status": 201,
            "isActive": True,
            "message": "User created successfully. Welcome!",
            "data": {
                "email_id": new_user.email,
                "access_token": access_token,
                "token_type": "bearer",
            }
        }

    except ValueError as ve:
        # Handle specific validation errors
        logging.error(f"Validation error during user creation: {ve}")
        return {
            "success": False,
            "status": 422,
            "isActive": False,
            "message": f"Invalid input: {str(ve)}",
            "data": None,
        }

    except Exception as e:
        # Rollback the transaction in case of an error
        logging.error(f"An unexpected error occurred during user creation: {e}")
        db.rollback()
        return {
            "success": False,
            "status": 500,
            "isActive": False,
            "message": "An unexpected error occurred. Please try again later.",
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
    try:
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
                detail="User not found. Ensure the token is valid and try again.",
            )

        # Check if the `profile_path` is valid (optional validation based on your requirements)
        if not profile_path or not profile_path.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid profile path provided. It cannot be empty.",
            )

        # Validate user's role and permissions
        if user.role == "admin":  # Admins can update anyone's profile path
            logging.info(f"Admin {user.email} is updating profile path.")
        elif user.email != email:  # Regular users can only update their own profile
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not authorized to update another user's profile path.",
            )

        # Update the profile path
        user.profile_path = profile_path

        # Commit the changes
        try:
            db.commit()
            db.refresh(user)
        except Exception as db_error:
            db.rollback()
            logging.error(f"Database commit error: {db_error}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An error occurred while updating the profile path. Please try again.",
            )

        # Return updated user info
        return schemas.UserResponse(
            success=True,
            status=200,
            isActive=user.status == schemas.UserStatus.active,
            message="User profile path updated successfully.",
            data=schemas.UserData(
                id=user.id,
                name=user.name,
                email=user.email,
                phone_number=user.phone_number or "",  # Ensure default value if None
                profile_path=user.profile_path,
                status=user.status,
                role=user.role,  # Include the user's role for transparency
            ),
        )

    except HTTPException as http_exc:
        # Re-raise any HTTP exceptions
        logging.warning(f"HTTP exception: {http_exc.detail}")
        raise http_exc

    except Exception as e:
        # Handle unexpected errors
        logging.error(f"Unexpected error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred. Please try again later.",
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
    try:
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
                detail="User not found. Please ensure your token is valid.",
            )

        # Validate the fields that can be updated
        for field, value in updated_info.dict(exclude_unset=True).items():
            if field == "name":
                # Ensure the name is valid (non-empty, non-null)
                if not value.strip():
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Name cannot be empty or only whitespace.",
                    )
                setattr(user, field, value)
            
            elif field == "phone_number":
                # Optional: Add validation for phone number format (if needed)
                if not value.strip():
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Phone number cannot be empty or only whitespace.",
                    )
                setattr(user, field, value)
            
            elif field == "profile_path":
                # Optional: Add validation for profile path (e.g., URL validation)
                if not value.strip():
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Profile path cannot be empty or only whitespace.",
                    )
                setattr(user, field, value)

            elif field == "role":
                # Prevent users from updating their own role
                if user.role != "admin":
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Regular users cannot update their role.",
                    )
                setattr(user, field, value)  # Admins can update roles

            else:
                # Handle unsupported fields
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Field '{field}' cannot be updated.",
                )

        # Commit the changes
        try:
            db.commit()
            db.refresh(user)
        except Exception as e:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An error occurred while updating the user information. Please try again.",
            )

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
                "phone_number": user.phone_number or "",  # Ensure default value if None
                "role": user.role,
                "profile_path": user.profile_path,
                "status": user.status,
            },
        }

    except HTTPException as http_exc:
        # Re-raise any HTTP exceptions
        logging.warning(f"HTTP exception: {http_exc.detail}")
        raise http_exc

    except Exception as e:
        # Handle unexpected errors
        logging.error(f"Unexpected error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred. Please try again later.",
        )
