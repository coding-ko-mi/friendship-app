"""
Сервис достижений — единая точка выдачи и чтения (модуль «Бэкенд: достижения»).

Разделение ответственности (важно для чистоты):
  • КОГДА выдавать — решает место события (group_service при создании компании
    и изменении состава, matching_service при первом мэтче). Там лежит
    продуктовое условие.
  • КАК выдавать и КАК читать — здесь. Один способ выдачи на весь проект:
    проверка справочника, идемпотентность, безопасность для транзакции.

Транзакция: при выдаче сервис НЕ коммитит. Он работает в той же сессии и
транзакции, что и вызвавший его сервис (FOUNDER выдаётся внутри create_group,
коммит делает create_group). Так создание компании и выдача атомарны.
Методы чтения (витрина) коммита не требуют — они только SELECT.
"""
from __future__ import annotations

import logging
from collections.abc import Iterable

from app.models.enums import AchievementCode
from app.repositories.achievement_repository import AchievementRepository
from app.schemas.achievements import AchievementCard, AchievementShowcase

logger = logging.getLogger(__name__)


class AchievementService:
    """Выдача достижений и чтение их для витрины."""

    def __init__(self, *, repo: AchievementRepository) -> None:
        self.repo = repo

    # ================================================================== #
    #  ВЫДАЧА (вызывается из мест событий)                               #
    # ================================================================== #
    async def grant(self, *, user_id: int, code: AchievementCode) -> bool:
        """
        Выдать одно достижение одному пользователю.

        Идемпотентно и безопасно:
          • если кода нет в справочнике (seed не прогнан) — тихо выходим (no-op),
            ядро не падает;
          • если достижение уже выдано — ничего не делаем;
          • иначе вставляем (flush, без commit — коммитит вызывающий сервис).

        Возвращает True, если достижение выдано именно сейчас (для будущего
        модуля «Бот»: по True можно прислать пуш «получено достижение»).
        False — если уже было или справочник пуст.
        """
        achievement = await self.repo.get_by_code(code.value)
        if achievement is None:
            # Справочник не наполнен этим кодом. Не падаем — достижения
            # не критичный путь. Логируем, чтобы заметить незапущенный seed.
            logger.warning(
                "Achievement code %s отсутствует в справочнике — выдача пропущена. "
                "Прогоните seed_achievements.",
                code.value,
            )
            return False

        if await self.repo.has(user_id=user_id, achievement_id=achievement.id):
            return False  # уже есть — повторно не выдаём

        await self.repo.add(user_id=user_id, achievement_id=achievement.id)
        return True

    async def grant_many(
        self, *, user_ids: Iterable[int], code: AchievementCode
    ) -> list[int]:
        """
        Выдать одно достижение нескольким пользователям (например, FULL_HOUSE —
        всей компании при достижении полного состава).

        Возвращает id тех, кому достижение выдано именно сейчас (кто его ещё
        не имел) — пригодится модулю «Бот» для адресных пушей.
        """
        newly_granted: list[int] = []
        for user_id in user_ids:
            if await self.grant(user_id=user_id, code=code):
                newly_granted.append(user_id)
        return newly_granted

    # ================================================================== #
    #  ЧТЕНИЕ (витрина достижений пользователя)                          #
    # ================================================================== #
    async def get_showcase(self, *, user_id: int) -> AchievementShowcase:
        """
        Собрать витрину достижений для пользователя.

        Возвращает ВЕСЬ справочник, помечая каждое как полученное (с датой) или
        ещё закрытое. Так фронтенд показывает и достигнутое, и цели впереди —
        это и есть петля вовлечённости. Когда ты добавишь новые достижения в
        seed, они автоматически появятся здесь как «закрытые».
        """
        catalog = await self.repo.list_all()
        earned = await self.repo.list_user(user_id)
        # achievement_id -> когда получено. Для быстрой пометки справочника.
        earned_at_by_id = {ua.achievement_id: ua.earned_at for ua in earned}

        cards = [
            AchievementCard(
                code=a.code,
                name=a.name,
                description=a.description,
                earned=a.id in earned_at_by_id,
                earned_at=earned_at_by_id.get(a.id),
            )
            for a in catalog
        ]

        return AchievementShowcase(
            achievements=cards,
            earned_count=len(earned_at_by_id),
            total_count=len(catalog),
        )
