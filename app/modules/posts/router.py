from fastapi import APIRouter, Depends, Query, UploadFile, File, Form, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.modules.posts.logic import (
    create_post_logic,
    get_post_by_id,
    get_all_posts_logic,
    update_post_logic,
    delete_post_logic,
    delete_post_image_logic,
)
from app.modules.posts.schemas import (
    PostCreateRequest,
    PostUpdateRequest,
    PostResponse,
    PostListResponse,
    PostAuthorInfo,
    PostTeamInfo,
    PostImageResponse,
)
from app.models.user import User

router = APIRouter(prefix="/posts", tags=["Posts"])


def build_post_response(post) -> PostResponse:
    """Строит ответ с данными поста"""
    author_username = post.author.username if post.author else "unknown"

    full_name = "Unknown"
    if post.author and hasattr(post.author, 'student') and post.author.student:
        student = post.author.student
        full_name = f"{student.surname} {student.name}"

    author_info = PostAuthorInfo(username=author_username, full_name=full_name)

    team_info = None
    if post.team:
        team_info = PostTeamInfo(id=post.team.id, name=post.team.name)

    images = [
        PostImageResponse(
            id=img.id,
            filename=img.filename,
            file_path=img.file_path,
            file_size=img.file_size,
            content_type=img.content_type,
            uploaded_at=img.uploaded_at,
        )
        for img in post.images
    ]

    return PostResponse(
        id=post.id,
        title=post.title,
        content=post.content,
        created_at=post.created_at,
        updated_at=post.updated_at,
        author=author_info,
        team=team_info,
        images=images,
    )


@router.post("/", response_model=PostResponse)
async def create_post(
        title: str = Form(..., min_length=1, max_length=200),
        content: str = Form(..., min_length=1, max_length=10000),
        files: List[UploadFile] = File(default=[]),
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
):
    """Создание нового поста"""
    data = PostCreateRequest(title=title, content=content)
    post = await create_post_logic(current_user, data, files, db)
    return build_post_response(post)


@router.get("/", response_model=PostListResponse)
async def get_posts(
        limit: int = Query(20, ge=1, le=100),
        offset: int = Query(0, ge=0),
        db: AsyncSession = Depends(get_db),
):
    """Получение списка всех постов с пагинацией"""
    posts, total = await get_all_posts_logic(db, limit=limit, offset=offset)
    return PostListResponse(posts=[build_post_response(p) for p in posts], total=total)


@router.get("/{post_id}", response_model=PostResponse)
async def get_post(post_id: int, db: AsyncSession = Depends(get_db)):
    """Получение поста по ID"""
    post = await get_post_by_id(post_id, db)
    return build_post_response(post)


@router.put("/{post_id}", response_model=PostResponse)
async def update_post(
        post_id: int,
        data: PostUpdateRequest,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
):
    """Обновление поста (только для автора)"""
    post = await update_post_logic(post_id, current_user, data, db)
    return build_post_response(post)


@router.delete("/{post_id}")
async def delete_post(
        post_id: int,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
):
    """Удаление поста (только для автора)"""
    await delete_post_logic(post_id, current_user, db)
    return {"message": "Пост успешно удалён"}


@router.delete("/{post_id}/images/{image_id}")
async def delete_post_image(
        post_id: int,
        image_id: int,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
):
    """Удаление изображения из поста"""
    await delete_post_image_logic(post_id, image_id, current_user, db)
    return {"message": "Изображение успешно удалено"}
