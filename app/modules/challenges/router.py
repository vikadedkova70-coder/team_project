from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.dependencies import get_current_user, get_current_captain, get_current_admin_or_teacher
from app.models.user import User
from app.models.team import Team
from sqlalchemy import select
from app.modules.challenges.logic import (
    get_challenges_logic,
    create_challenge_logic,
    enroll_challenge_logic,
    complete_challenge_logic,
    get_team_challenges_logic,
    delete_challenge_logic
)
from app.modules.challenges.schemas import (
    ChallengeResponse,
    ChallengeCreateRequest,
    TeamChallengeResponse,
    EnrollmentAction
)

router = APIRouter(prefix="/challenges", tags=["Challenges"])


@router.get("")
async def list_challenges(
    status: str = Query("active"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db)
):
    """Список челленджей"""
    challenges, total = await get_challenges_logic(status, limit, offset, db)
    return {
        "challenges": [
            ChallengeResponse(
                id=c.id,
                title=c.title,
                description=c.description,
                reward_points=c.reward_points,
                deadline=c.deadline,
                created_at=c.created_at,
                is_active=c.is_active
            )
            for c in challenges
        ],
        "total": total
    }


@router.post("")
async def create_challenge(
    data: ChallengeCreateRequest,
    current_user: User = Depends(get_current_admin_or_teacher),
    db: AsyncSession = Depends(get_db)
):
    """Создание челленджа (админ/преподаватель)"""
    challenge = await create_challenge_logic(
        title=data.title,
        description=data.description,
        reward_points=data.reward_points,
        deadline=data.deadline,
        db=db
    )
    return ChallengeResponse(
        id=challenge.id,
        title=challenge.title,
        description=challenge.description,
        reward_points=challenge.reward_points,
        deadline=challenge.deadline,
        created_at=challenge.created_at,
        is_active=challenge.is_active
    )


@router.post("/{challenge_id}/enroll")
async def enroll_to_challenge(
    challenge_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Запись команды на челлендж"""
    from app.models.team import TeamMember
    membership_result = await db.execute(
        select(TeamMember).where(TeamMember.user_id == current_user.id)
    )
    membership = membership_result.scalar_one_or_none()
    if not membership:
        raise HTTPException(status_code=400, detail="Вы не состоите в команде")

    enrollment = await enroll_challenge_logic(challenge_id, membership.team_id, db)
    return {"message": "Запись на челлендж оформлена", "enrollment_id": enrollment.id}


@router.post("/{challenge_id}/complete")
async def complete_challenge(
    challenge_id: int,
    current_user: User = Depends(get_current_captain),
    db: AsyncSession = Depends(get_db)
):
    """Завершение челленджа (капитан)"""
    enrollment = await complete_challenge_logic(challenge_id, current_user.id, db)
    return {"message": "Челлендж завершён", "enrollment_id": enrollment.id}


@router.get("/my")
async def get_my_challenges(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Челленджи моей команды"""
    from app.models.team import TeamMember
    membership_result = await db.execute(
        select(TeamMember).where(TeamMember.user_id == current_user.id)
    )
    membership = membership_result.scalar_one_or_none()
    if not membership:
        return {"challenges": []}

    team_challenges = await get_team_challenges_logic(membership.team_id, db)
    return {
        "challenges": [
            {
                "id": tc.id,
                "challenge": ChallengeResponse(
                    id=tc.challenge.id,
                    title=tc.challenge.title,
                    description=tc.challenge.description,
                    reward_points=tc.challenge.reward_points,
                    deadline=tc.challenge.deadline,
                    created_at=tc.challenge.created_at,
                    is_active=tc.challenge.is_active
                ),
                "team_id": tc.team_id,
                "status": tc.status,
                "enrolled_at": tc.enrolled_at,
                "completed_at": tc.completed_at
            }
            for tc in team_challenges
        ]
    }


@router.delete("/{challenge_id}")
async def remove_challenge(
    challenge_id: int,
    current_user: User = Depends(get_current_admin_or_teacher),
    db: AsyncSession = Depends(get_db)
):
    """Удаление челленджа (админ/преподаватель)"""
    await delete_challenge_logic(challenge_id, db)
    return {"message": "Челлендж удалён"}
