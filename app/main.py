import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.core.database import engine, Base, AsyncSessionLocal
from app.core.config import settings
from app.modules.auth.router import router as auth_router
from app.modules.team.router import router as team_router
from app.models.user import Student, User, UserRole
from app.models.team import Team, TeamMember, TeamInviteLink, TeamJoinRequest
from sqlalchemy import select
from app.modules.posts.router import router as posts_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Функция жизненного цикла приложения"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    if settings.DEMO_MODE:
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Student).where(Student.id == 123))
            if not result.scalar_one_or_none():
                student = Student(
                    id=123,
                    surname="Иванов",
                    name="Иван",
                    patronymic="Иванович"
                )
                session.add(student)

                from app.core.security import get_password_hash
                user = User(
                    student_id=123,
                    username="ivanov_test",
                    password_hash=get_password_hash("test123"),
                    role=UserRole.CAPTAIN.value
                )
                session.add(user)
                await session.commit()
                print("Демо-данные созданы: никнейм 'ivanov_test', пароль 'test123', роль: капитан")

            result = await session.execute(select(Student).where(Student.id == 124))
            if not result.scalar_one_or_none():
                student_petrov = Student(
                    id=124,
                    surname="Петров",
                    name="Пётр",
                    patronymic="Петрович"
                )
                session.add(student_petrov)
                await session.commit()
                print("Доп. демо-данные: студент Петров (id=124) без аккаунта")

    yield


app = FastAPI(title="University API", lifespan=lifespan)

app.include_router(auth_router)
app.include_router(team_router)
app.include_router(posts_router)


@app.get("/")
async def root():
    """Простая проверка, что сервер работает"""
    return {"message": "API работает! Открой /docs"}


if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8080, reload=True)