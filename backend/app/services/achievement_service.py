"""
Сервис достижений — бизнес-логика геймификации.

Отвечает за:
  • выдачу достижения по коду (идемпотентно: повтор не падает и не дублирует);
  • сбор витрины (весь справочник + флаг earned для пользователя);
  • вычисление пороговых условий компании (NO_BORDERS, FULL_HOUSE) —
    «выдать ли и кому», чтобы вызывающий сервис компаний не знал деталей.

Ключевое решение по идемпотентности (см. handoff): grant() возвращает bool —
True, если достижение выдано ВПЕРВЫЕ, False, если уже было. Это позволяет
звать выдачу из любого места без страха упасть, и при этом понимать, нужно ли
слать пуш (пуш — только при True, иначе спам при каждом пересчёте).

Транспорт (HTTP) и Redis сюда не лезут: сервис лишь меняет состояние БД через
репозиторий и СООБЩАЕТ вызывающему, что выдано впервые. Отправку пуша делает
вызывающий сервис ПОСЛЕ commit (так требует контракт events.py: не уведомлять
о незафиксированном). Так выдача остаётся в одной транзакции с созданием
компании/мэтча, а пуш — уже после неё.
"""
from __future__ import annotations

from app.models.enums import AchievementCode
from app.repositories.achievement_repository import AchievementRepository
from app.schemas.achievements import (
    AchievementCard,
    AchievementsResponse,
    EarnedAchievement,
)


class AchievementService:
    """Выдача достижений и сбор витрины прогресса."""

    def __init__(self, *, achievement_repo: AchievementRepository) -> None:
        self.achievement_repo = achievement_repo

    # ================================================================== #
    #  ВЫДАЧА                                                            #
    # ================================================================== #
    async def grant(self, *, user_id: int, code: str) -> bool:
        """
        Выдать пользователю достижение по коду. Идемпотентно.

        Возвращает:
          • True  — достижение выдано ВПЕРВЫЕ (повод слать пуш);
          • False — уже было раньше ИЛИ кода нет в справочнике (seed не прогнан).

        Почему не бросаем исключение при отсутствии кода: выдача вызывается из
        критических путей (создание компании, мэтч). Незаполненный справочник —
        проблема развёртывания, а не повод ронять создание компании. Тихо
        возвращаем False и не мешаем основному сценарию.

        Транзакцию НЕ коммитим: выдача должна попасть в commit вызывающего
        сервиса (атомарно с созданием компании/мэтча).
        """
        achievement_id = await self.achievement_repo.get_id_by_code(code)
        if achievement_id is None:
            # Кода нет в справочнике — выдавать нечего (seed не прогнан).
            return False

        # Проверяем ДО вставки: так отличаем «выдано впервые» от «уже было»,
        # не полагаясь на перехват ошибки PK (что усложнило бы управление
        # транзакцией — пойманный IntegrityError помечает сессию rollback-only).
        if await self.achievement_repo.has(
            user_id=user_id, achievement_id=achievement_id
        ):
            return False

        await self.achievement_repo.add(
            user_id=user_id, achievement_id=achievement_id
        )
        return True

    async def grant_many(self, *, user_ids: list[int], code: str) -> list[int]:
        """
        Выдать одно достижение нескольким пользователям (пороговые: NO_BORDERS,
        FULL_HOUSE выдаются ВСЕМ участникам компании).

        Возвращает список user_id, которым достижение выдано ВПЕРВЫЕ — именно им
        вызывающий сервис отправит пуш (тем, у кого уже было, — не шлём).
        """
        granted_first_time: list[int] = []
        for user_id in user_ids:
            if await self.grant(user_id=user_id, code=code):
                granted_first_time.append(user_id)
        return granted_first_time

    # ================================================================== #
    #  ПОРОГОВЫЕ УСЛОВИЯ КОМПАНИИ                                        #
    # ================================================================== #
    # Вынесены сюда (а не в group_service), чтобы вся логика «что считается
    # достижением» жила в одном модуле. group_service лишь поставляет факты
    # о составе (id участников, их города, размер) и зовёт эти методы.
    @staticmethod
    def is_no_borders(member_cities: list[str]) -> bool:
        """
        Условие «Без границ»: в компании есть люди из 2+ разных городов.

        Принимаем готовый список городов участников (group_service умеет их
        достать), чтобы сервис достижений не лез в чужой репозиторий.
        """
        return len(set(member_cities)) >= 2

    @staticmethod
    def is_full_house(member_count: int, *, threshold: int) -> bool:
        """
        Условие «Полный состав»: компания достигла порога участников.

        threshold берётся из config (FULL_HOUSE_SIZE) — точное число (8/10) ещё
        уточняется тестированием, поэтому хранится в одном настраиваемом месте,
        а не зашито здесь.
        """
        return member_count >= threshold

    # ================================================================== #
    #  ВИТРИНА                                                           #
    # ================================================================== #
    async def get_showcase(self, user_id: int) -> AchievementsResponse:
        """
        Собрать витрину: весь справочник достижений + флаг earned (и дата) для
        конкретного пользователя.

        Один проход: берём справочник, берём полученные достижения пользователя,
        склеиваем по achievement_id. Так фронт получает полную карту прогресса
        (и полученное, и «ещё не открытое») за один запрос.
        """
        catalog = await self.achievement_repo.list_all()
        earned_links = await self.achievement_repo.list_earned(user_id)

        # achievement_id -> earned_at, чтобы проставить дату полученным.
        earned_at_by_id = {link.achievement_id: link.earned_at for link in earned_links}

        items = [
            AchievementCard(
                code=a.code,
                name=a.name,
                description=a.description,
                icon=a.icon,
                earned=a.id in earned_at_by_id,
                earned_at=earned_at_by_id.get(a.id),
            )
            for a in catalog
        ]

        return AchievementsResponse(
            items=items,
            earned_count=len(earned_at_by_id),
            total=len(catalog),
        )

    async def list_earned_public(self, user_id: int) -> list[EarnedAchievement]:
        """
        Список заработанных достижений пользователя для публичной анкеты.

        В отличие от витрины (get_showcase), сюда попадают ТОЛЬКО уже
        полученные — недостигнутые в чужой анкете не показываем, чтобы не
        раскрывать прогресс. Порядок — как в справочнике (стабильный для UI).
        """
        catalog = await self.achievement_repo.list_all()
        earned_ids = await self.achievement_repo.list_earned_ids(user_id)
        return [
            EarnedAchievement(
                code=a.code,
                name=a.name,
                description=a.description,
                icon=a.icon,
            )
            for a in catalog
            if a.id in earned_ids
        ]
