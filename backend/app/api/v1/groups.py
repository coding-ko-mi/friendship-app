"""
REST-эндпоинты модуля «Компании + голосование» (сценарий Б).

  POST /api/v1/groups                      — создать компанию (из мэтча)
  GET  /api/v1/groups/{group_id}           — карточка компании + состав
  GET  /api/v1/groups/{group_id}/requests  — активные заявки компании (для голосующих)
  POST /api/v1/groups/{group_id}/requests  — подать заявку (join / invite / merge)
  GET  /api/v1/requests/{request_id}        — статус заявки + прогресс голосов
  POST /api/v1/requests/{request_id}/vote   — проголосовать

Роутер — тонкий: разбирает запрос, собирает сервис через Depends, ловит
доменные ошибки и превращает их в HTTP. Вся логика — в GroupService.

Примечание о префиксе: единый стиль с остальными роутерами проекта (auth,
profiles, questionnaire, discovery) — короткий префикс в роутере, а `/api/v1`
добавляется в main.py через include_router(prefix="/api/v1"). Объявлены ДВА
роутера: groups_router (`/groups`) и requests_router (`/requests`).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

# Зависимость из модуля «Бэкенд: ядро» (контракт из git_status_handoff_2.md):
#   get_current_user — достаёт текущего User по JWT (Telegram-авторизация).
# Если в реальном коде путь/имя иные — поправить только этот импорт.
from app.api.deps import get_current_user
from app.database import get_session
from app.models.user import User
from app.redis_client import get_redis
from app.repositories.achievement_repository import AchievementRepository
from app.repositories.group_repository import GroupRepository
from app.schemas.groups import (
    GroupCard,
    GroupCreate,
    GroupSummary,
    RequestCard,
    RequestCreate,
    VoteResult,
)
from app.services.achievement_service import AchievementService
from app.services.group_service import (
    ConflictError,
    GroupService,
    NotFoundError,
    PermissionError_,
    ValidationError_,
)

# Короткие префиксы; /api/v1 добавляется в main.py (как у auth/profiles/discovery).
groups_router = APIRouter(prefix="/groups", tags=["groups"])
requests_router = APIRouter(prefix="/requests", tags=["groups"])


# --------------------------------------------------------------------- #
#  Сборка сервиса (внедрение зависимостей)                              #
# --------------------------------------------------------------------- #
def get_group_service(
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> GroupService:
    """
    Собрать GroupService с его репозиторием.

    Сервис не знает, откуда берётся session/redis — их подставляет FastAPI.
    Так сервис остаётся тестируемым (в тестах подставим фейковые зависимости).
    """
    return GroupService(
        group_repo=GroupRepository(session),
        # AchievementService собирается на ТОЙ ЖЕ сессии → выдача FOUNDER и
        # пороговых (NO_BORDERS, FULL_HOUSE) идёт в одной транзакции с
        # изменением состава компании.
        achievement_service=AchievementService(
            achievement_repo=AchievementRepository(session)
        ),
        redis=redis,
    )


def _to_http(error: Exception) -> HTTPException:
    """
    Единое отображение доменных ошибок в HTTP-коды.

    Держим маппинг в одном месте, чтобы все эндпоинты отвечали одинаково.
    """
    if isinstance(error, NotFoundError):
        return HTTPException(status.HTTP_404_NOT_FOUND, detail=str(error))
    if isinstance(error, PermissionError_):
        return HTTPException(status.HTTP_403_FORBIDDEN, detail=str(error))
    if isinstance(error, ConflictError):
        return HTTPException(status.HTTP_409_CONFLICT, detail=str(error))
    if isinstance(error, ValidationError_):
        return HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(error))
    # Непредвиденная доменная ошибка — 400 как безопасный дефолт.
    return HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(error))


# ===================================================================== #
#  КОМПАНИИ                                                             #
# ===================================================================== #
@groups_router.get("", response_model=list[GroupSummary])
async def list_my_groups(
    current_user: User = Depends(get_current_user),
    service: GroupService = Depends(get_group_service),
) -> list[GroupSummary]:
    """
    Компании текущего пользователя (для экрана «Матчи → Компании»).

    Лёгкий список без подгрузки состава. Детальная карточка с участниками
    открывается отдельным GET /groups/{id} при тапе.
    """
    pairs = await service.group_repo.list_groups_of_user(current_user.id)
    return [
        GroupSummary(id=g.id, name=g.name, member_count=cnt) for g, cnt in pairs
    ]


@groups_router.post("", response_model=GroupCard, status_code=status.HTTP_201_CREATED)
async def create_group(
    payload: GroupCreate,
    current_user: User = Depends(get_current_user),
    service: GroupService = Depends(get_group_service),
) -> GroupCard:
    """
    Создать компанию из подтверждённого мэтча.

    Текущий пользователь становится основателем; партнёр по мэтчу добавляется
    автоматически. Компания рождается из 2 человек.
    """
    try:
        return await service.create_group(
            founder=current_user, name=payload.name, match_id=payload.match_id
        )
    except (NotFoundError, PermissionError_, ConflictError, ValidationError_) as e:
        raise _to_http(e) from e


@groups_router.get("/{group_id}", response_model=GroupCard)
async def get_group(
    group_id: int,
    current_user: User = Depends(get_current_user),
    service: GroupService = Depends(get_group_service),
) -> GroupCard:
    """Карточка компании со списком участников."""
    try:
        return await service.get_group_card(group_id)
    except NotFoundError as e:
        raise _to_http(e) from e


@groups_router.get("/{group_id}/requests", response_model=list[RequestCard])
async def list_group_requests(
    group_id: int,
    current_user: User = Depends(get_current_user),
    service: GroupService = Depends(get_group_service),
) -> list[RequestCard]:
    """
    Активные заявки, по которым голосует эта компания.

    Это то, что участники компании видят и по чему голосуют.
    """
    return await service.get_group_requests(group_id)


@groups_router.post(
    "/{group_id}/requests",
    response_model=RequestCard,
    status_code=status.HTTP_201_CREATED,
)
async def create_request(
    group_id: int,
    payload: RequestCreate,
    current_user: User = Depends(get_current_user),
    service: GroupService = Depends(get_group_service),
) -> RequestCard:
    """
    Подать заявку на изменение состава компании {group_id} (это target-компания).

      join   — subject_user_id просится в компанию (подаёт сам пользователь);
      invite — компания зовёт subject_user_id (подаёт участник компании);
      merge  — subject_group_id вливается в компанию (подаёт участник любой из двух).
    """
    try:
        return await service.create_request(
            current_user=current_user,
            target_group_id=group_id,
            type_=payload.type,
            subject_user_id=payload.subject_user_id,
            subject_group_id=payload.subject_group_id,
        )
    except (NotFoundError, PermissionError_, ConflictError, ValidationError_) as e:
        raise _to_http(e) from e


# ===================================================================== #
#  ЗАЯВКИ И ГОЛОСОВАНИЕ                                                  #
# ===================================================================== #
@requests_router.get("/{request_id}", response_model=RequestCard)
async def get_request(
    request_id: int,
    current_user: User = Depends(get_current_user),
    service: GroupService = Depends(get_group_service),
) -> RequestCard:
    """Статус заявки и прогресс голосования по каждой голосующей компании."""
    try:
        return await service.get_request_card(request_id)
    except NotFoundError as e:
        raise _to_http(e) from e


@requests_router.post("/{request_id}/vote", response_model=VoteResult)
async def vote(
    request_id: int,
    value: bool = Query(..., description="true = «за», false = «против»"),
    current_user: User = Depends(get_current_user),
    service: GroupService = Depends(get_group_service),
) -> VoteResult:
    """
    Проголосовать по заявке.

    Голосовать вправе только участник компании, которая решает по этой заявке
    (для merge — участник любой из двух). Повторный голос запрещён. Если этот
    голос определяет исход — заявка автоматически принимается/отклоняется,
    и (при принятии) состав компании изменяется. Пуш о результате — модуль «Бот».
    """
    try:
        return await service.vote(
            current_user=current_user, request_id=request_id, value=value
        )
    except (NotFoundError, PermissionError_, ConflictError, ValidationError_) as e:
        raise _to_http(e) from e
