import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy import text
from app.main import app
from app.core.database import Base, get_db
from app.models.user import Student, User, UserRole
from app.models.team import Team, TeamMember #потом понадобится
from app.core.security import get_password_hash

TEST_DB = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture(scope="function")
async def client():
    """Фикстура для создания тестового клиента и базы данных"""
    engine = create_async_engine(TEST_DB, echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    test_session = AsyncSession(engine, expire_on_commit=False)

    await test_session.execute(text("DELETE FROM team_members"))
    await test_session.execute(text("DELETE FROM team_join_requests"))
    await test_session.execute(text("DELETE FROM team_invite_links"))
    await test_session.execute(text("DELETE FROM teams"))
    await test_session.execute(text("DELETE FROM users"))
    await test_session.execute(text("DELETE FROM students"))
    await test_session.commit()

    # Студент 1: Иванов — капитан
    student_ivanov = Student(id=123, surname="Иванов", name="Иван", patronymic="Иванович")
    test_session.add(student_ivanov)

    user_ivanov = User(
        student_id=123,
        username="ivanov_captain",
        password_hash=get_password_hash("CaptainPass123!"),
        role=UserRole.CAPTAIN.value
    )
    test_session.add(user_ivanov)

    # Студент 2: Петров — обычный студент
    student_petrov = Student(id=124, surname="Петров", name="Пётр", patronymic="Петрович")
    test_session.add(student_petrov)

    user_petrov = User(
        student_id=124,
        username="petrov_student",
        password_hash=get_password_hash("StudentPass123!"),
        role=UserRole.STUDENT.value
    )
    test_session.add(user_petrov)

    await test_session.commit()

    async def override_get_db():
        yield test_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
    await test_session.close()
    await engine.dispose()


@pytest.mark.asyncio
async def test_get_profile(client):
    """Тест получения профиля пользователя"""
    login = await client.post("/auth/login", json={
        "username": "ivanov_captain",
        "password": "CaptainPass123!"
    })
    assert login.status_code == 200
    token = login.json()["access_token"]

    profile = await client.get("/team/profile", headers={
        "Authorization": f"Bearer {token}"
    })
    assert profile.status_code == 200
    data = profile.json()
    assert data["username"] == "ivanov_captain"
    assert data["role"] == "captain"
    assert data["team_name"] is None


@pytest.mark.asyncio
async def test_create_team(client):
    """Тест создания команды капитаном"""
    login = await client.post("/auth/login", json={
        "username": "ivanov_captain",
        "password": "CaptainPass123!"
    })
    token = login.json()["access_token"]

    create = await client.post("/team/create", json={
        "name": "Test Team",
        "description": "Test description"
    }, headers={"Authorization": f"Bearer {token}"})

    assert create.status_code == 200
    data = create.json()
    assert data["name"] == "Test Team"
    assert data["captain_id"] == 1

    profile = await client.get("/team/profile", headers={"Authorization": f"Bearer {token}"})
    assert profile.json()["team_name"] == "Test Team"


@pytest.mark.asyncio
async def test_search_teams(client):
    """Тест поиска команд"""
    login = await client.post("/auth/login", json={
        "username": "ivanov_captain",
        "password": "CaptainPass123!"
    })
    token = login.json()["access_token"]

    await client.post("/team/create", json={
        "name": "Alpha Team",
        "description": "Alpha"
    }, headers={"Authorization": f"Bearer {token}"})

    search = await client.get("/team/search?query=Alpha")
    assert search.status_code == 200
    teams = search.json()
    assert len(teams) == 1
    assert teams[0]["name"] == "Alpha Team"


@pytest.mark.asyncio
async def test_join_by_link(client):
    """Тест вступления в команду по ссылке"""
    # Капитан создаёт команду и ссылку
    captain_login = await client.post("/auth/login", json={
        "username": "ivanov_captain",
        "password": "CaptainPass123!"
    })
    captain_token = captain_login.json()["access_token"]

    create = await client.post("/team/create", json={
        "name": "Link Team",
        "description": "Test"
    }, headers={"Authorization": f"Bearer {captain_token}"})
    team_id = create.json()["id"]

    invite = await client.post(f"/team/{team_id}/invite", json={
        "expires_hours": 24
    }, headers={"Authorization": f"Bearer {captain_token}"})
    assert invite.status_code == 200
    token = invite.json()["token"]

    # Студент вступает по ссылке... Зачем ссылке нужны данные студента... Безопасность вышла из чата 2
    student_login = await client.post("/auth/login", json={
        "username": "petrov_student",
        "password": "StudentPass123!"
    })
    student_token = student_login.json()["access_token"]

    join = await client.post("/team/join-by-link", json={
        "token": token
    }, headers={"Authorization": f"Bearer {student_token}"})

    assert join.status_code == 200
    assert join.json()["team_name"] == "Link Team"


@pytest.mark.asyncio
async def test_join_request_flow(client):
    """Тест подачи и обработки заявки на вступление"""
    # Капитан создаёт команду
    captain_login = await client.post("/auth/login", json={
        "username": "ivanov_captain",
        "password": "CaptainPass123!"
    })
    captain_token = captain_login.json()["access_token"]

    create = await client.post("/team/create", json={
        "name": "Request Team",
        "description": "Test"
    }, headers={"Authorization": f"Bearer {captain_token}"})
    team_id = create.json()["id"]

    # Студент отправляет заявку
    student_login = await client.post("/auth/login", json={
        "username": "petrov_student",
        "password": "StudentPass123!"
    })
    student_token = student_login.json()["access_token"]

    request = await client.post(f"/team/{team_id}/join-request", headers={
        "Authorization": f"Bearer {student_token}"
    })
    assert request.status_code == 200
    request_id = request.json()["request_id"]

    # Капитан видит заявку
    requests = await client.get(f"/team/{team_id}/requests", headers={
        "Authorization": f"Bearer {captain_token}"
    })
    assert requests.status_code == 200
    assert len(requests.json()) == 1

    # Капитан принимает заявку
    process = await client.post(f"/team/requests/{request_id}/process", json={
        "action": "approve"
    }, headers={"Authorization": f"Bearer {captain_token}"})
    assert process.status_code == 200

    # Студент теперь в команде
    profile = await client.get("/team/profile", headers={"Authorization": f"Bearer {student_token}"})
    assert profile.json()["team_name"] == "Request Team"

# именно в плане, что хотят от меня функции и что возвращать, пока не ясно...
# но, просматривая код и конкретно тесты, +- идеи появляются, надо бы потом их обсудить и не забыть
