from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException, status
from app.models.user import Student, User
from app.core.security import create_access_token, get_password_hash, decode_token, verify_password
from app.modules.auth.schemas import VerifyRequest
from app.core.config import settings
from datetime import timedelta


async def verify_student_logic(data: VerifyRequest, db: AsyncSession) -> dict:
    """Проверка студенческого билета: если аккаунт есть - предлагаем войти, если нет - выдаём токен регистрации"""
    query = select(Student).where(Student.id == data.student_id)
    result = await db.execute(query)
    student = result.scalar_one_or_none()

    if not student:
        raise HTTPException(status_code=404, detail="Студент не найден")

    user_query = select(User).where(User.student_id == student.id)
    existing_user = (await db.execute(user_query)).scalar_one_or_none()

    if existing_user:
        return {
            "exists": True,
            "verification_token": None,
            "message": "Аккаунт найден, выполните вход"
        }

    token = create_access_token(
        data={"sub": str(student.id), "scope": "verification"},
        expires_delta=timedelta(minutes=5)
    )

    return {
        "exists": False,
        "verification_token": token,
        "message": "Студент найден, зарегистрируйтесь"
    }


async def register_user_logic(token: str, username: str, password: str, confirm_password: str, db: AsyncSession) -> dict:
    """Регистрация пользователя после верификации"""
    if password != confirm_password:
        raise HTTPException(status_code=400, detail="Пароли не совпадают")

    payload = decode_token(token)
    if not payload or payload.get("scope") != "verification":
        raise HTTPException(status_code=400, detail="Неверный токен")

    student_id = int(payload.get("sub"))

    existing_user = await db.execute(select(User).where(User.username == username))
    if existing_user.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Никнейм уже занят")

    hashed = get_password_hash(password)
    new_user = User(student_id=student_id, username=username, password_hash=hashed)

    db.add(new_user)
    await db.commit()

    return {"message": "Регистрация успешна", "username": username}


async def login_user_logic(username: str, password: str, db: AsyncSession) -> tuple[str, User]:
    """Вход в систему, проверка пароля и выдача токена доступа"""
    query = select(User).where(User.username == username)
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=401, detail="Неверный никнейм или пароль")

    if not user.is_active:
        raise HTTPException(status_code=400, detail="Аккаунт заблокирован")

    token = create_access_token(
        data={"sub": str(user.student_id), "username": user.username, "role": user.role},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    return token, user
