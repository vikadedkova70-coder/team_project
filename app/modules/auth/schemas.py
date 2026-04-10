from pydantic import BaseModel, Field


class VerifyRequest(BaseModel):
    """Данные для верификации студента"""
    student_id: int
    surname: str
    name: str
    patronymic: str


class VerifyResponse(BaseModel):
    """Ответ после успешной верификации"""
    verification_token: str
    message: str = "Верификация успешна"


class RegisterRequest(BaseModel):
    """Данные для регистрации (после верификации)"""
    verification_token: str  # Токен, полученный на шаге верификации
    # Никнейм: 3-50 символов, только латиница, цифры и подчёркивание
    username: str = Field(..., min_length=3, max_length=50, pattern=r'^[a-zA-Z0-9_]+$')
    password: str = Field(..., min_length=6)


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