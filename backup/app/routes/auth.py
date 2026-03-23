from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from backup.app.schemas import UserResponse, Token
from backup.database.db import get_db
from backup.database import models_db as models
from backup.core.auth import auth_logic

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/register", response_model=UserResponse)
async def register_team(
    team_name: str, 
    email: str, 
    password: str,
    db: Session = Depends(get_db)):
    """
    Register a new team in the database.
    """
    # Check if user already exists
    existing_user = db.query(models.User).filter(
        (models.User.email == email) | 
        (models.User.team_name == team_name)
    ).first()
    
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Team name or team email already exists",
        )

    # Create new user with hashed password
    new_user = models.User(
        team_name=team_name,
        email=email,
        password_hash=auth_logic.hash_password(password)
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@router.post("/login", response_model=Token)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(), 
    db: Session = Depends(get_db)
):
    """
    Authenticate a team and return a JWT access token.
    - The 'username' field in the form should be the user's email.
    """
    user = db.query(models.User).filter(models.User.email == form_data.username).first()
    
    #password verification
    if not user or not auth_logic.verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    #generate the token
    access_token = auth_logic.create_access_token(data={"sub": str(user.id)})
    
    return {"access_token": access_token, "token_type": "bearer"}