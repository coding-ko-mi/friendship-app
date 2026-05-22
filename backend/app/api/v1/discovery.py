"""
REST-эндпоинты модуля «Мэтчинг» (сценарий А: одиночка ↔ одиночка).

  GET  /api/v1/discovery/feed        — лента кандидатов (свайпы)
  POST /api/v1/discovery/like        — лайкнуть кандидата (+ авто-мэтч)
  POST /api/v1/discovery/skip        — скипнуть кандидата (скрыть на время)

Роутер — тонкий: разбирает запрос, собирает сервис через Depends, ловит
доменные ошибки и превращает их в HTTP. Вся логика — в MatchingService.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

# Зависимости из модуля «Бэкенд: ядро» (контракт из git_status_handoff_1.md):
#   get_current_user — достаёт текущего User по JWT (Telegram-авторизация).
# Если в реальном коде путь/имя иные — поправить только этот импорт.
from app.api.deps import get_current_user
from app.config import DISCOVERY_PAGE_SIZE
from app.database import get_session
from app.models.user import User
from app.redis_client import get_redis
from app.repositories.matching_repository import MatchingRepository
from app.repositories.skip_repository import SkipRepository
from app.schemas.matching import DiscoveryFeed, LikeResult, SkipResult
from app.services.matching_service import (
    MatchingService,
    SelfActionError,
    TargetNotFoundError,
)

router = APIRouter(prefix="/discovery", tags=["discovery"])

# --------------------------------------------------------------------- #
#  Сборка сервиса (внедрение зависимостей)                              #
# --------------------------------------------------------------------- #
def get_matching_service(
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> MatchingService:
    """
    Собрать MatchingService с его репозиториями.

    Сервис не знает, откуда берутся session/redis — их подставляет FastAPI.
    Так сервис остаётся тестируемым (в тестах подставим фейковые репозитории).
    """
    return MatchingService(
        matching_repo=MatchingRepository(session),
        skip_repo=SkipRepository(redis),
    )


async def get_partner_age_range(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> tuple[int, int]:
    """
    Диапазон возраста кандидатов из анкеты пользователя (partner_age_min/max).

    Анкета (Questionnaire) — из модуля «Бэкенд: ядро». Если поля не заполнены,
    берём дефолт 18–100 (показываем всех по возрасту, фильтр де-факто выключен).

    ВНИМАНИЕ (точка стыковки с модулем «ядро»): здесь предполагается, что есть
    QuestionnaireRepository с методом get_by_user_id. Если в реальном коде доступ
    к анкете называется иначе — меняется только это тело функции, остальной
    модуль мэтчинга трогать не нужно.
    """
    from app.repositories.questionnaire_repository import QuestionnaireRepository

    questionnaire = await QuestionnaireRepository(session).get_by_user_id(
        current_user.id
    )
    if questionnaire is None:
        return 18, 100

    age_min = questionnaire.partner_age_min or 18
    age_max = questionnaire.partner_age_max or 100
    return age_min, age_max


# --------------------------------------------------------------------- #
#  Эндпоинты                                                            #
# --------------------------------------------------------------------- #
@router.get("/feed", response_model=DiscoveryFeed)
async def get_feed(
    cursor: int | None = Query(
        default=None,
        description="id последнего показанного кандидата (для подгрузки следующей порции)",
    ),
    limit: int = Query(
        default=DISCOVERY_PAGE_SIZE,
        ge=1,
        le=50,
        description="сколько кандидатов вернуть за раз",
    ),
    current_user: User = Depends(get_current_user),
    age_range: tuple[int, int] = Depends(get_partner_age_range),
    service: MatchingService = Depends(get_matching_service),
) -> DiscoveryFeed:
    """Лента кандидатов: отфильтрована по городу/возрасту, отсортирована по интересам."""
    age_min, age_max = age_range
    return await service.get_feed(
        current_user=current_user,
        age_min=age_min,
        age_max=age_max,
        cursor=cursor,
        limit=limit,
    )


@router.post("/like", response_model=LikeResult)
async def like_user(
    to_user_id: int = Query(..., description="id кандидата, которого лайкаем"),
    current_user: User = Depends(get_current_user),
    service: MatchingService = Depends(get_matching_service),
) -> LikeResult:
    """
    Лайкнуть кандидата. Если встречный лайк уже есть — создаётся мэтч
    (is_mutual=true, match_id заполнен). Пуш о мэтче отправит модуль «Бот».
    """
    try:
        return await service.like(from_user=current_user, to_user_id=to_user_id)
    except SelfActionError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except TargetNotFoundError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(e)) from e


@router.post("/skip", response_model=SkipResult)
async def skip_user(
    skipped_user_id: int = Query(..., description="id кандидата, которого скипаем"),
    current_user: User = Depends(get_current_user),
    service: MatchingService = Depends(get_matching_service),
) -> SkipResult:
    """Скрыть кандидата из ленты на время (свайп влево). В БД ничего не пишет."""
    try:
        return await service.skip(
            from_user=current_user, skipped_user_id=skipped_user_id
        )
    except SelfActionError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
