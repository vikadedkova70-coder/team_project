import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy import text
from app.main import app
from app.core.database import Base, get_db
from app.models.user import Student, User
from app.core.security import get_password_hash

# SQLite, чтобы быстро проверить
TEST_DB = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture(scope="function")
async def client():
    # 1. Тут движок для тестов
    engine = create_async_engine(TEST_DB, echo=False)

    # 2. Сами таблицы
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # 3. Одна сессия на весь тест (много не надо, думаю... Хотя потом надо бы несколько раз прогонять мб)
    test_session = AsyncSession(engine, expire_on_commit=False)

    # 4. Очистка таблицы, чтобы лишнего не было
    await test_session.execute(text("DELETE FROM users"))
    await test_session.execute(text("DELETE FROM students"))
    await test_session.commit()

    # 5. Есть два студента:
    #    - (крутой стандарт) Иванов (123): уже с аккаунтом
    #    - (его дополнение) Петров (124): без аккаунта (но он есть в базе студентов)

    # Иванов уже зарегистрирован
    student_ivanov = Student(id=123, surname="Иванов", name="Иван", patronymic="Иванович")
    test_session.add(student_ivanov)

    user_ivanov = User(
        student_id=123,
        username="ivanov_user",
        password_hash=get_password_hash("IvanovPass123!")
    )
    test_session.add(user_ivanov)

    # Петров — нет
    student_petrov = Student(id=124, surname="Петров", name="Пётр", patronymic="Петрович")
    test_session.add(student_petrov)

    await test_session.commit()

    # 6. Подмена зависимости get_db (надо бы потом получше с этим разобраться)
    async def override_get_db():
        yield test_session

    app.dependency_overrides[get_db] = override_get_db

    # 7. Создаём тестовый клиент с новым синтаксисом httpx >= 0.27
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    # 8. Убираем подмену и чистим ресы
    app.dependency_overrides.clear()
    await test_session.close()
    await engine.dispose()
# Зачем записала шаги, что мы делаем? Потому что как делать тесты не шарю пока

@pytest.mark.asyncio
async def test_verify_success(client):
    """Тест простой верификации (Петров без аккаунта)"""
    resp = await client.post("/auth/verify", json={
        "student_id": 124
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["exists"] == False
    assert data["verification_token"] is not None


@pytest.mark.asyncio
async def test_full_registration_flow(client):
    """Полный тест: верификация -> регистрация -> вход (для Петрова)"""

    # --- Шаг 1: Верификация Петрова ---
    print("\n[TEST] 1. Верификация Петрова...")
    v = await client.post("/auth/verify", json={
        "student_id": 124
    })
    print(f"   Статус: {v.status_code}")
    assert v.status_code == 200, f"Верификация не удалась: {v.text}"
    verification_token = v.json()["verification_token"]

    # --- Шаг 2: Регистрация Петрова ---
    print("[TEST] 2. Регистрация Петрова...")
    r = await client.post("/auth/register", json={
        "verification_token": verification_token,
        "username": "petrov_user",
        "password": "PetrovPass123!",
        "confirm_password": "PetrovPass123!"
    })
    print(f"   Статус: {r.status_code}, Ответ: {r.json()}")
    assert r.status_code == 200, f"Регистрация не удалась: {r.text}"

    # --- Шаг 3: Вход Петрова ---
    print("[TEST] 3. Вход Петрова...")
    l = await client.post("/auth/login", json={
        "username": "petrov_user",
        "password": "PetrovPass123!"
    })
    print(f"   Статус: {l.status_code}, Ответ: {l.json()}")
    assert l.status_code == 200, f"Вход не удался: {l.text}"
    assert "access_token" in l.json()

    print("\nТест регистрации Петрова пройден!")


@pytest.mark.asyncio
async def test_two_students_different_status(client):
    """
    Тест сценария:
    - Иванов (123) уже имеет аккаунт → должен уметь войти
    - Петров (124) не имеет аккаунта → должен уметь зарегистрироваться
    """

    print("\n" + "=" * 60)
    print("[TEST] Сценарий: Два студента с разным статусом")
    print("=" * 60)

    # 🔹 Часть 1: Иванов (уже зарегистрирован) — проверяем вход
    print("\n[1/4] Иванов: попытка входа (аккаунт уже есть)...")
    login_ivanov = await client.post("/auth/login", json={
        "username": "ivanov_user",
        "password": "IvanovPass123!"
    })
    print(f"   Статус: {login_ivanov.status_code}")
    assert login_ivanov.status_code == 200, f"Иванов не смог войти: {login_ivanov.text}"
    ivanov_token = login_ivanov.json()["access_token"]
    print("   Иванов успешно вошёл")

    # 🔹 Часть 2: Петров (не зарегистрирован) — проверяем, что нельзя войти
    print("\n[2/4] Петров: попытка входа без регистрации (должно отказать)...")
    login_petrov_fail = await client.post("/auth/login", json={
        "username": "petrov_user",
        "password": "AnyPassword123!"
    })
    print(f"   Статус: {login_petrov_fail.status_code}")
    assert login_petrov_fail.status_code == 401, "Петров не должен иметь возможность войти без регистрации"
    print("   Петрову корректно отказано во входе")

    # 🔹 Часть 3: Петров проходит верификацию
    print("\n[3/4] Петров: верификация...")
    verify_petrov = await client.post("/auth/verify", json={
        "student_id": 124
    })
    assert verify_petrov.status_code == 200
    petrov_verify_token = verify_petrov.json()["verification_token"]
    print("   Петров верифицирован")

    # 🔹 Часть 4: Петров регистрируется и входит
    print("\n[4/4] Петров: регистрация и вход...")

    # Регистрация
    register_petrov = await client.post("/auth/register", json={
        "verification_token": petrov_verify_token,
        "username": "petrov_user",
        "password": "PetrovPass123!",
        "confirm_password": "PetrovPass123!"
    })
    assert register_petrov.status_code == 200
    print("   Петров зарегистрирован")

    # Вход
    login_petrov_success = await client.post("/auth/login", json={
        "username": "petrov_user",
        "password": "PetrovPass123!"
    })
    assert login_petrov_success.status_code == 200
    petrov_token = login_petrov_success.json()["access_token"]
    print("   Петров успешно вошёл")

    # + проверка профилей обоих студентов... не знаю, что тут надо, поэтому пока будут токены
    # Безопасность вышла из чата
    print("\nПроверка профилей...")

    # Профиль Иванова
    profile_ivanov = await client.get("/auth/me", headers={
        "Authorization": f"Bearer {ivanov_token}"
    })
    assert profile_ivanov.status_code == 200
    assert profile_ivanov.json()["username"] == "ivanov_user"
    assert profile_ivanov.json()["student_id"] == 123
    print(f"   Профиль Иванова: {profile_ivanov.json()}")

    # Профиль Петрова
    profile_petrov = await client.get("/auth/me", headers={
        "Authorization": f"Bearer {petrov_token}"
    })
    assert profile_petrov.status_code == 200
    assert profile_petrov.json()["username"] == "petrov_user"
    assert profile_petrov.json()["student_id"] == 124
    print(f"   Профиль Петрова: {profile_petrov.json()}")

    print("\nТест 'Два студента' пройден полностью!")


@pytest.mark.asyncio
async def test_cannot_register_twice(client):
    """
    Тест защиты: если студент уже зарегистрирован,
    верификация должна вернуть exists=True без токена
    """
    print("\n[TEST] Защита: повторная регистрация...")

    # Иванов уже зарегистрирован в фикстуре
    # Пытаемся верифицировать его снова
    verify = await client.post("/auth/verify", json={
        "student_id": 123
    })

    # Теперь возвращается 200 с exists=True и message "Аккаунт найден"
    assert verify.status_code == 200
    data = verify.json()
    assert data["exists"] == True
    assert data["verification_token"] is None
    assert "Аккаунт найден" in data["message"]
    print("   Система корректно сообщает что аккаунт уже есть")

