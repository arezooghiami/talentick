"""
Talentick — Auth Router
POST /api/auth/login
GET  /api/auth/me
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import CurrentUser
from app.schemas.auth import LoginRequest, TokenResponse
from app.services import auth_service

router = APIRouter(
    prefix="/api/auth",
    tags=["Authentication"]
)


from fastapi.security import OAuth2PasswordRequestForm


@router.post("/login", response_model=TokenResponse)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    user = await auth_service.authenticate_user(
        db,
        form_data.username,
        form_data.password,
    )

    if not user:
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials",
        )

    return auth_service.build_token(user)


@router.get("/me")
async def me(current_user: CurrentUser):
    return {
        "id": str(current_user.id),
        "org_id": str(current_user.org_id),
        "email": current_user.email,
        "full_name": current_user.full_name,
        "role": current_user.role,
        "is_active": current_user.is_active,
    }

