from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from fastapi import HTTPException
from app.models.activity import Challenge, TeamChallenge, Activity
from app.models.rating import TeamRatingLog
from app.models.team import Team
from app.models.user import User
from app.modules.challenges.schemas import ChallengeResponse, TeamChallengeResponse
from datetime import datetime, timedelta


DEFAULT_RATING = 3.0
MAX_RATING = 5.0
MIN_RATING = 0.0
POINTS_TO_RATING_RATIO = 0.1


async def get_challenges_logic(
    status: str = "active",
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession = None
) -> tuple[list[Challenge], int]:
    """Получение списка челленджей"""
    query = select(Challenge)
    if status == "active":
        query = query.where(Challenge.is_active == True)

    result = await db.execute(
        query.order_by(Challenge.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    challenges = result.scalars().all()

    count_result = await db.execute(select(Challenge))
    total = len(count_result.scalars().all())

    return challenges, total


async def create_challenge_logic(
    title: str,
    description: str | None,
    reward_points: int,
    deadline: datetime | None,
    db: AsyncSession = None
) -> Challenge:
    """Создание челленджа (только для админов/преподавателей)"""
    challenge = Challenge(
        title=title,
        description=description,
        reward_points=reward_points,
        deadline=deadline,
        is_active=True
    )
    db.add(challenge)
    await db.commit()
    await db.refresh(challenge)
    return challenge


async def enroll_challenge_logic(
    challenge_id: int,
    team_id: int,
    db: AsyncSession = None
) -> TeamChallenge:
    """Запись команды на челлендж"""
    challenge = await db.get(Challenge, challenge_id)
    if not challenge or not challenge.is_active:
        raise HTTPException(status_code=404, detail="Челлендж не найден или неактивен")

    team = await db.get(Team, team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Команда не найдена")

    existing = await db.execute(
        select(TeamChallenge).where(
            TeamChallenge.challenge_id == challenge_id,
            TeamChallenge.team_id == team_id
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Команда уже записана на этот челлендж")

    enrollment = TeamChallenge(
        challenge_id=challenge_id,
        team_id=team_id,
        status="active"
    )
    db.add(enrollment)
    await db.commit()
    await db.refresh(enrollment)
    return enrollment


async def complete_challenge_logic(
    challenge_id: int,
    team_id: int,
    db: AsyncSession = None
) -> TeamChallenge:
    """Завершение челленджа командой"""
    enrollment_result = await db.execute(
        select(TeamChallenge).where(
            TeamChallenge.challenge_id == challenge_id,
            TeamChallenge.team_id == team_id
        )
    )
    enrollment = enrollment_result.scalar_one_or_none()
    if not enrollment:
        raise HTTPException(status_code=404, detail="Нет записи на этот челлендж")
    if enrollment.status == "completed":
        raise HTTPException(status_code=400, detail="Челлендж уже завершён")

    challenge = await db.get(Challenge, challenge_id)
    team = await db.get(Team, team_id)

    enrollment.status = "completed"
    enrollment.completed_at = datetime.utcnow()

    old_rating = team.rating
    delta = challenge.reward_points * POINTS_TO_RATING_RATIO
    new_rating = min(MAX_RATING, old_rating + delta)
    team.rating = new_rating

    rating_log = TeamRatingLog(
        team_id=team_id,
        event_type="challenge_completed",
        old_rating=old_rating,
        new_rating=new_rating,
        description=f'Завершён челлендж "{challenge.title}" (+{delta:.2f})'
    )
    db.add(rating_log)

    activity = Activity(
        team_id=team_id,
        event_type="challenge_completed",
        title=f'Челлендж завершён: {challenge.title}',
        description=f'Получено {challenge.reward_points} баллов, рейтинг: {old_rating:.2f} → {new_rating:.2f}',
        metadata={"challenge_id": challenge_id, "reward_points": challenge.reward_points}
    )
    db.add(activity)

    await db.commit()
    await db.refresh(enrollment)
    return enrollment


async def get_team_challenges_logic(
    team_id: int,
    db: AsyncSession = None
) -> list[TeamChallenge]:
    """Получение всех челленджей команды"""
    result = await db.execute(
        select(TeamChallenge)
        .where(TeamChallenge.team_id == team_id)
        .options(selectinload(TeamChallenge.challenge))
        .order_by(TeamChallenge.enrolled_at.desc())
    )
    return result.scalars().all()


async def delete_challenge_logic(
    challenge_id: int,
    db: AsyncSession = None
) -> None:
    """Удаление челленджа (только для админов/преподавателей)"""
    challenge = await db.get(Challenge, challenge_id)
    if not challenge:
        raise HTTPException(status_code=404, detail="Челлендж не найден")

    await db.delete(challenge)
    await db.commit()