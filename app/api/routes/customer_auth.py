from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from db.session import get_db
from app.core.dependencies import get_current_customer
from app.schemas.auth import (
    CustomerRegisterRequest, CustomerLoginRequest,
    TokenResponse, RefreshRequest, ForgotPasswordRequest,
    ResetPasswordRequest, CustomerResponse
)
from app.services.customer_auth_service import customer_auth_service
from app.core.rate_limit import enforce_login_rate_limit
from app.models.customer import CustomerAccount

router = APIRouter(prefix="/customer-auth", tags=["Auth - Customer"])


@router.post("/register", response_model=TokenResponse)
def register(payload: CustomerRegisterRequest, db: Session = Depends(get_db)):
    customer = customer_auth_service.register(db, payload.name, payload.phone, payload.password, payload.email)
    db.commit()
    db.refresh(customer)
    return customer_auth_service.create_tokens(customer)


@router.post("/login", response_model=TokenResponse)
def login(payload: CustomerLoginRequest, request: Request, db: Session = Depends(get_db)):
    enforce_login_rate_limit(request, "customer_login")
    customer = customer_auth_service.authenticate(db, payload.login, payload.password)
    return customer_auth_service.create_tokens(customer)


@router.post("/refresh", response_model=TokenResponse)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)):
    return customer_auth_service.refresh_tokens(db, payload.refresh_token)


@router.get("/me", response_model=CustomerResponse)
def me(current_customer: CustomerAccount = Depends(get_current_customer)):
    return current_customer


@router.post("/forgot-password")
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)):
    customer = db.query(CustomerAccount).filter(
        CustomerAccount.email == payload.email, CustomerAccount.is_active == True
    ).first()
    if customer:
        customer_auth_service.create_reset_token(db, customer)
        db.commit()
    return {"message": "Se o e-mail existir, você receberá as instruções de redefinição."}


@router.post("/reset-password")
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    customer_auth_service.reset_password(db, payload.token, payload.new_password)
    db.commit()
    return {"message": "Senha redefinida com sucesso."}
