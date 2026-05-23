"""
Registration router — завершение гибридной регистрации.

  POST /api/v1/registration   создать User из фото (Redis) + анкеты (Mini App)

Почему отдельный роутер, а не часть auth: auth выдаёт токены и сообщает
is_registered. Создание профиля — отдельная ответственность (анкета + интересы),
и она единственная, кто пишет нового User в БД.

ВАЖНО (точка стыковки с модулем «ядро»):
  Обычные эндпоинты используют get_current_user → User. Но регистрирующийся
  пользователь ещё НЕ имеет строки User, поэтому get_current_user здесь не
  годится (ему некого вернуть). Вместо этого мы принимаем сырой initData и
  достаём из него telegram_id тем же проверенным механизмом, что auth/telegram.

  Контракт: validate_init_data проверяет HMAC-SHA256 подпись и возвращает dict
  с ключом "id" (telegram_id пользователя).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import Field
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.redis_client import get_redis
from app.schemas.registration import RegistrationRequest, RegistrationResponse
from app.services.registration_service import (
    AlreadyRegisteredError,
    PhotoNotFoundError,
    RegistrationService,
    UnknownInterestError,
)
from app.core.telegram_auth import validate_init_data

router = APIRouter(prefix="/registration", tags=["registration"])


class RegistrationBody(RegistrationRequest):
    """
    Тело запроса регистрации = поля анкеты + initData для авторизации.

    init_data передаётся отдельно от полей анкеты: это подписанная Telegram
    строка (window.Telegram.WebApp.initData), из неё сервер берёт telegram_id.
    Так клиент физически не может подставить чужой telegram_id.
    """

    init_data: str = Field(description="window.Telegram.WebApp.initData (подпись Telegram)")


def _get_service(
    db: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> RegistrationService:
    return RegistrationService(session=db, redis=redis)


@router.post("", response_model=RegistrationResponse, status_code=status.HTTP_201_CREATED)
async def register(
    body: RegistrationBody,
    service: RegistrationService = Depends(_get_service),
) -> RegistrationResponse:
    """
    Завершить регистрацию пользователя.

    Поток (гибрид, Вариант A):
      • фото уже прислано боту и лежит в Redis (pending_photo:{telegram_id});
      • здесь приходят остальные поля анкеты + initData;
      • сервис достаёт фото из Redis и создаёт User одним INSERT.
    """
    # Достаём telegram_id из подписанной строки initData (не из тела запроса).
    try:
        telegram_user = validate_init_data(body.init_data)
        telegram_id = int(telegram_user["id"])
    except (KeyError, ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Некорректный initData.",
        )

    # Поля анкеты — это всё тело, КРОМЕ init_data. Собираем «чистый»
    # RegistrationRequest, отбросив init_data (он только для авторизации).
    data = RegistrationRequest(
        name=body.name,
        age=body.age,
        about=body.about,
        city=body.city,
        interest_ids=body.interest_ids,
    )

    try:
        return await service.register(telegram_id=telegram_id, data=data)
    except AlreadyRegisteredError as e:
        # 409: профиль уже есть — фронт ведёт пользователя сразу в приложение.
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except PhotoNotFoundError as e:
        # 422: нет фото — фронт возвращает пользователя в бота прислать фото.
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except UnknownInterestError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
