from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from db.session import get_db
from app.core.dependencies import get_current_user
from app.schemas.auth import LoginRequest, TokenResponse, RefreshRequest, ForgotPasswordRequest, ResetPasswordRequest, UserResponse
from app.services.auth_service import auth_service
from app.core.rate_limit import enforce_login_rate_limit
from app.models.user import User

router = APIRouter(prefix="/auth", tags=["Auth - Internal"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    enforce_login_rate_limit(request, "internal_login")
    user = auth_service.authenticate(db, payload.email, payload.password)
    return auth_service.create_tokens(user)


@router.post("/refresh", response_model=TokenResponse)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)):
    return auth_service.refresh_tokens(db, payload.refresh_token)


@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)):
    return UserResponse.from_user(current_user)


@router.post("/forgot-password")
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email, User.is_active == True).first()
    if user:
        token = auth_service.create_reset_token(db, user)
        db.commit()
        # In production: send email with reset link
    return {"message": "Se o e-mail existir, você receberá as instruções de redefinição."}


@router.post("/reset-password")
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    auth_service.reset_password(db, payload.token, payload.new_password)
    db.commit()
    return {"message": "Senha redefinida com sucesso."}
