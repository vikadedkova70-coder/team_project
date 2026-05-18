import os
import uuid
from pathlib import Path
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from fastapi import HTTPException, status, UploadFile
from app.models.user import User, Student
from app.models.team import Team, TeamMember
from app.models.post import Post, PostImage
from app.modules.posts.schemas import PostCreateRequest, PostUpdateRequest
from datetime import datetime, timezone
import shutil

UPLOAD_DIR = Path("uploads/posts")


async def ensure_upload_dir():
    """Создаёт директорию для загрузок, если её нет"""
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def save_uploaded_file(file: UploadFile, post_id: int) -> tuple[str, str, int]:
    """Сохраняет загруженный файл и возвращает информацию о нём"""
    file_extension = Path(file.filename).suffix.lower() if file.filename else ".jpg"
    unique_filename = f"{uuid.uuid4().hex}{file_extension}"
    file_path = UPLOAD_DIR / unique_filename

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    file_size = file_path.stat().st_size
    return file.filename or "unknown", str(file_path), file_size


async def get_user_team(user: User, db: AsyncSession) -> Optional[Team]:
    """Получает команду пользователя"""
    membership = await db.execute(
        select(TeamMember).where(TeamMember.user_id == user.id)
    )
    membership = membership.scalar_one_or_none()
    if membership:
        return await db.get(Team, membership.team_id)
    return None


async def _load_post_with_relations(post_id: int, db: AsyncSession) -> Post:
    """Вспомогательная функция: загружает пост со всеми отношениями"""
    result = await db.execute(
        select(Post)
        .where(Post.id == post_id)
        .options(
            selectinload(Post.images),
            selectinload(Post.author),
            selectinload(Post.team)
        )
    )
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=404, detail="Пост не найден")
    return post


async def create_post_logic(
        user: User,
        data: PostCreateRequest,  # <- Имя параметра + тип
        files: List[UploadFile],
        db: AsyncSession
) -> Post:
    """Создание нового поста"""
    await ensure_upload_dir()
    team = await get_user_team(user, db)

    post = Post(
        title=data.title,
        content=data.content,
        author_id=user.id,
        team_id=team.id if team else None
    )

    db.add(post)
    await db.flush()

    if files:
        for file in files:
            if not file.filename:
                continue
            if file.content_type and not file.content_type.startswith("image/"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Файл {file.filename} не является изображением"
                )

            file.file.seek(0, 2)
            file_size = file.file.tell()
            file.file.seek(0)

            if file_size > 5 * 1024 * 1024:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Файл {file.filename} слишком большой (максимум 5MB)"
                )

            original_filename, file_path, size = save_uploaded_file(file, post.id)
            post_image = PostImage(
                post_id=post.id,
                filename=original_filename,
                file_path=file_path,
                file_size=size,
                content_type=file.content_type or "image/jpeg"
            )
            db.add(post_image)

    await db.commit()
    return await _load_post_with_relations(post.id, db)


async def get_post_by_id(post_id: int, db: AsyncSession) -> Post:
    """Получение поста по ID"""
    return await _load_post_with_relations(post_id, db)


async def get_all_posts_logic(
        db: AsyncSession,
        limit: int = 20,
        offset: int = 0
) -> tuple[list, int]:
    """Получение всех постов с пагинацией"""
    total_result = await db.execute(select(func.count(Post.id)))
    total = total_result.scalar()

    result = await db.execute(
        select(Post)
        .options(
            selectinload(Post.images),
            selectinload(Post.author),
            selectinload(Post.team)
        )
        .order_by(Post.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    posts = result.scalars().all()
    return posts, total


async def update_post_logic(
        post_id: int,
        user: User,
        data: PostUpdateRequest,  # <- Имя параметра + тип
        db: AsyncSession
) -> Post:
    """Обновление поста (только автор может редактировать)"""
    post = await get_post_by_id(post_id, db)

    if post.author_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Только автор может редактировать пост"
        )

    if data.title is not None:
        post.title = data.title
    if data.content is not None:
        post.content = data.content

    post.updated_at = datetime.now(timezone.utc)

    await db.commit()
    return await _load_post_with_relations(post_id, db)


async def delete_post_logic(
        post_id: int,
        user: User,
        db: AsyncSession
) -> bool:
    """Удаление поста (только автор может удалить)"""
    post = await get_post_by_id(post_id, db)

    if post.author_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Только автор может удалить пост"
        )

    for image in post.images:
        image_path = Path(image.file_path)
        if image_path.exists():
            image_path.unlink()

    await db.delete(post)
    await db.commit()
    return True


async def delete_post_image_logic(
        post_id: int,
        image_id: int,
        user: User,
        db: AsyncSession
) -> bool:
    """Удаление изображения из поста"""
    post = await get_post_by_id(post_id, db)

    if post.author_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Только автор может удалять изображения"
        )

    image = next((img for img in post.images if img.id == image_id), None)
    if not image:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Изображение не найдено"
        )

    image_path = Path(image.file_path)
    if image_path.exists():
        image_path.unlink()

    await db.delete(image)
    await db.commit()
    return True
