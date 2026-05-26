"""
Сервис регистрации — бизнес-логика гибридной регистрации (Вариант A).

Здесь принимаются продуктовые решения:
  • откуда берётся фото (Redis-ключ pending_photo:{telegram_id}, положенный ботом);
  • что делать, если фото нет (пользователь не прошёл шаг с фото в боте);
  • что делать при повторной регистрации (уже есть User с таким telegram_id);
  • валидация интересов против справочника.

Транспорт (HTTP) и доступ к БД сюда не лезут напрямую — сервис оркеструет
репозиторий + Redis и возвращает готовую схему. Это единственное место,
которое пишет нового User в БД (бот в БД не пишет вообще).

Ключ Redis намеренно совпадает с тем, что пишет бот
(app/bot/services/pending_photo.py) — это контракт между двумя процессами.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import EARLY_BIRD_WINDOW_DAYS, LAUNCH_DATE
from app.models.enums import AchievementCode
from app.repositories.achievement_repository import AchievementRepository
from app.repositories.registration_repository import RegistrationRepository
from app.schemas.registration import RegistrationRequest, RegistrationResponse
from app.services.achievement_service import AchievementService
from app.services.events import achievement_event, enqueue_event


# --------------------------------------------------------------------- #
#  Доменные ошибки (роутер превратит их в HTTP-ответы)                  #
# --------------------------------------------------------------------- #
class RegistrationError(Exception):
    """Базовая ошибка домена регистрации."""


class AlreadyRegisteredError(RegistrationError):
    """Пользователь с таким telegram_id уже зарегистрирован."""


class PhotoNotFoundError(RegistrationError):
    """
    Нет ожидающего фото в Redis.

    Значит пользователь не прошёл шаг с фото в боте (или фото истекло по TTL).
    Фронт должен вернуть его в бота прислать фото заново.
    """


class UnknownInterestError(RegistrationError):
    """Среди interest_ids есть id, которого нет в справочнике."""


# Формат ключа должен ПОБУКВЕННО совпадать с ботом (pending_photo.py).
# Держим формат в одном месте — функцией, чтобы не разойтись со стороной бота.
def pending_photo_key(telegram_id: int) -> str:
    """Redis-ключ, под которым бот сохраняет file_id ожидающего фото."""
    return f"pending_photo:{telegram_id}"


class RegistrationService:
    """Создание пользователя из фото (Redis) + анкеты (Mini App)."""

    def __init__(self, *, session: AsyncSession, redis: Redis) -> None:
        self.repo = RegistrationRepository(session)
        self.session = session
        self.redis = redis

    async def register(
        self, *, telegram_id: int, data: RegistrationRequest
    ) -> RegistrationResponse:
        """
        Завершить регистрацию: собрать User из фото (Redis) и анкеты (запрос).

        Порядок проверок выстроен от дешёвых к дорогим и от «нельзя продолжать»
        к деталям:
          1. Уже зарегистрирован? → ошибка (повторная регистрация запрещена).
          2. Есть ли ожидающее фото в Redis? → нет → вернуть в бота.
          3. Все ли интересы существуют в справочнике? → нет → ошибка.
          4. Создать User + связи, удалить фото из Redis, закоммитить.
        """
        # 1. Повторная регистрация запрещена — анкета создаётся один раз.
        existing = await self.repo.get_by_telegram_id(telegram_id)
        if existing is not None:
            raise AlreadyRegisteredError("Пользователь уже зарегистрирован")

        # 2. Фото должно ждать в Redis (его положил бот на шаге с фото).
        photo_file_id = await self.redis.get(pending_photo_key(telegram_id))
        if not photo_file_id:
            raise PhotoNotFoundError(
                "Фото не найдено. Вернитесь в бота и пришлите фото заново."
            )

        # 3. Валидируем интересы против справочника (свободный ввод запрещён).
        interests = await self.repo.get_existing_interests(data.interest_ids)
        if len(interests) != len(set(data.interest_ids)):
            raise UnknownInterestError("Среди интересов есть несуществующий id")

        # 4. Создаём пользователя (одним INSERT — все поля NOT NULL заполнены).
        user = await self.repo.create_user(
            telegram_id=telegram_id,
            name=data.name,
            age=data.age,
            about=data.about,
            photo_file_id=photo_file_id,
            city=data.city,
            interests=interests,
        )

        # EARLY_BIRD: «один из первых» — регистрация в окне после запуска.
        # Выдача идёт В ТУ ЖЕ транзакцию, что и создание пользователя, чтобы
        # гарантировать атомарность. Пуш — после commit.
        early_bird_granted = await self._maybe_grant_early_bird(user_id=user.id)

        await self.session.commit()

        # Фото больше не «ожидающее» — удаляем ключ, чтобы не висел до TTL.
        # Делаем ПОСЛЕ успешного коммита: если запись упадёт, фото останется
        # и человек сможет повторить регистрацию, не присылая фото снова.
        await self.redis.delete(pending_photo_key(telegram_id))

        if early_bird_granted:
            await enqueue_event(
                self.redis,
                achievement_event(user_id=user.id, achievement_name="Ранняя пташка"),
            )

        return RegistrationResponse(id=user.id, name=user.name)

    async def _maybe_grant_early_bird(self, *, user_id: int) -> bool:
        """
        Выдать EARLY_BIRD, если регистрация пришлась на окно после запуска.

        Окно: [LAUNCH_DATE, LAUNCH_DATE + EARLY_BIRD_WINDOW_DAYS].

        Парсим LAUNCH_DATE из конфига (ISO-строка). При битом значении —
        тихо не выдаём (не блокируем регистрацию из-за опечатки в .env).
        Возвращает True, если выдано впервые (=> повод слать пуш).
        """
        try:
            launch = date.fromisoformat(LAUNCH_DATE)
        except ValueError:
            # Неправильный формат LAUNCH_DATE — не блокируем регистрацию.
            return False

        # Сравниваем по дате (без времени): окно — это «N дней с запуска».
        today = datetime.now(timezone.utc).date()
        window_end = launch + timedelta(days=EARLY_BIRD_WINDOW_DAYS)
        if not (launch <= today <= window_end):
            return False

        # AchievementService собирается на ТОЙ ЖЕ сессии, что и репозиторий
        # регистрации — выдача попадёт в один commit с созданием User.
        ach_service = AchievementService(
            achievement_repo=AchievementRepository(self.session)
        )
        return await ach_service.grant(
            user_id=user_id, code=AchievementCode.EARLY_BIRD.value
        )
