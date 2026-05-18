from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.modules.auth.logic import verify_student_logic, register_user_logic, login_user_logic
from app.modules.auth.schemas import (
    VerifyRequest, VerifyResponse,
    RegisterRequest, LoginRequest,
    Token, UserResponse
)
from app.core.dependencies import get_current_user
from app.models.user import User

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/verify", response_model=VerifyResponse)
async def verify_endpoint(data: VerifyRequest, db: AsyncSession = Depends(get_db)):
    result = await verify_student_logic(data, db)
    return VerifyResponse(**result)


@router.post("/register")
async def register_endpoint(data: RegisterRequest, db: AsyncSession = Depends(get_db)):
    return await register_user_logic(
        data.verification_token,
        data.username,
        data.password,
        data.confirm_password,
        db
    )

@router.post("/login", response_model=Token)
async def login_endpoint(data: LoginRequest, db: AsyncSession = Depends(get_db)):
    token, _ = await login_user_logic(data.username, data.password, db)
    return Token(access_token=token)


@router.get("/me", response_model=UserResponse)
async def get_me(
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    """Получение данных текущего пользователя (защищённый эндпоинт)"""
    # Связь student уже загружена благодаря selectinload в get_current_user
    if current_user.student:
        full_name = f"{current_user.student.surname} {current_user.student.name} {current_user.student.patronymic}"
    else:
        full_name = "Unknown"

    return UserResponse(
        username=current_user.username,
        student_id=current_user.student_id,
        full_name=full_name
    )
