from pydantic import BaseModel, Field


class VerifyRequest(BaseModel):
    """Проверка студенческого билета"""
    student_id: int


class VerifyResponse(BaseModel):
    """Ответ после проверки студенческого билета"""
    exists: bool  # True если аккаунт уже есть, False если нужно регистрироваться
    verification_token: str | None = None  # Токен выдаётся только если аккаунта нет
    message: str


class RegisterRequest(BaseModel):
    """Данные для регистрации (после проверки)"""
    verification_token: str
    username: str = Field(..., min_length=3, max_length=50, pattern=r'^[a-zA-Z0-9_]+$')
    password: str = Field(..., min_length=6)
    confirm_password: str


class LoginRequest(BaseModel):
    """Данные для входа"""
    username: str
    password: str


class Token(BaseModel):
    """Стандартный ответ с токеном"""
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    """Информация о пользователе для профиля"""
    username: str
    student_id: int
    full_name: str
