import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy import text
from app.main import app
from app.core.database import Base, get_db
from app.models.user import Student, User, UserRole
from app.models.team import Team, TeamMember
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
        role=UserRole.CAPTAIN.value,
    )
    test_session.add(user_ivanov)

    # Студент 2: Петров — обычный студент
    student_petrov = Student(id=124, surname="Петров", name="Пётр", patronymic="Петрович")
    test_session.add(student_petrov)
    user_petrov = User(
        student_id=124,
        username="petrov_student",
        password_hash=get_password_hash("StudentPass123!"),
        role=UserRole.STUDENT.value,
    )
    test_session.add(user_petrov)

    # Создаём команду для Иванова
    team = Team(id=1, name="Test Team", description="Test", captain_id=1)
    test_session.add(team)
    await test_session.commit()

    membership = TeamMember(user_id=1, team_id=1)
    test_session.add(membership)
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
async def test_create_post_without_images(client):
    """Тест создания поста без изображений"""
    login = await client.post("/auth/login", json={
        "username": "ivanov_captain",
        "password": "CaptainPass123!"
    })
    assert login.status_code == 200
    token = login.json()["access_token"]

    # Используем form-data, а не JSON!
    create = await client.post("/posts/", data={
        "title": "Мой первый пост",
        "content": "Это содержание поста"
    }, headers={"Authorization": f"Bearer {token}"})

    if create.status_code != 200:
        print(f"❌ Ошибка: {create.status_code} - {create.json()}")

    assert create.status_code == 200
    data = create.json()
    assert data["title"] == "Мой первый пост"
    assert data["content"] == "Это содержание поста"
    assert data["author"]["username"] == "ivanov_captain"
    assert data["team"]["name"] == "Test Team"


@pytest.mark.asyncio
async def test_get_all_posts(client):
    """Тест получения списка постов"""
    login = await client.post("/auth/login", json={
        "username": "ivanov_captain",
        "password": "CaptainPass123!"
    })
    token = login.json()["access_token"]

    await client.post("/posts/", data={
        "title": "Post 1",
        "content": "Content 1"
    }, headers={"Authorization": f"Bearer {token}"})

    await client.post("/posts/", data={
        "title": "Post 2",
        "content": "Content 2"
    }, headers={"Authorization": f"Bearer {token}"})

    get_posts = await client.get("/posts/")
    assert get_posts.status_code == 200
    data = get_posts.json()
    assert data["total"] >= 2  # Может быть больше из-за других тестов


@pytest.mark.asyncio
async def test_update_post(client):
    """Тест обновления поста"""
    login = await client.post("/auth/login", json={
        "username": "ivanov_captain",
        "password": "CaptainPass123!"
    })
    token = login.json()["access_token"]

    create = await client.post("/posts/", data={
        "title": "Original Title",
        "content": "Original Content"
    }, headers={"Authorization": f"Bearer {token}"})

    assert create.status_code == 200
    post_id = create.json()["id"]

    update = await client.put(f"/posts/{post_id}", json={
        "title": "Updated Title",
        "content": "Updated Content"
    }, headers={"Authorization": f"Bearer {token}"})

    assert update.status_code == 200
    assert update.json()["title"] == "Updated Title"


@pytest.mark.asyncio
async def test_delete_post(client):
    """Тест удаления поста"""
    login = await client.post("/auth/login", json={
        "username": "ivanov_captain",
        "password": "CaptainPass123!"
    })
    token = login.json()["access_token"]

    create = await client.post("/posts/", data={
        "title": "Post to delete",
        "content": "Content"
    }, headers={"Authorization": f"Bearer {token}"})

    assert create.status_code == 200
    post_id = create.json()["id"]

    delete = await client.delete(f"/posts/{post_id}", headers={"Authorization": f"Bearer {token}"})
    assert delete.status_code == 200

    get_post = await client.get(f"/posts/{post_id}")
    assert get_post.status_code == 404


@pytest.mark.asyncio
async def test_cannot_update_others_post(client):
    """Тест что нельзя редактировать чужой пост"""
    login_ivanov = await client.post("/auth/login", json={
        "username": "ivanov_captain",
        "password": "CaptainPass123!"
    })
    ivanov_token = login_ivanov.json()["access_token"]

    create = await client.post("/posts/", data={
        "title": "Ivanov's post",
        "content": "Content"
    }, headers={"Authorization": f"Bearer {ivanov_token}"})

    assert create.status_code == 200
    post_id = create.json()["id"]

    login_petrov = await client.post("/auth/login", json={
        "username": "petrov_student",
        "password": "StudentPass123!"
    })
    petrov_token = login_petrov.json()["access_token"]

    update = await client.put(f"/posts/{post_id}", json={
        "title": "Hacked!"
    }, headers={"Authorization": f"Bearer {petrov_token}"})

    assert update.status_code == 403

