/**
 * Типизированные вызовы эндпоинтов бэкенда — ВСЕ контракты в одном месте.
 *
 * ЗАЧЕМ: компоненты и сервисы не пишут пути/методы руками. Если бэк меняет
 * эндпоинт — правка здесь, и TypeScript сразу покажет всех потребителей.
 * Каждый вызов сверен с реальным роутером бэка (комментарий-источник).
 */
import { API_PREFIX } from '../config';
import { request } from './client';
import type {
  AchievementsResponse,
  DiscoveryFeed,
  GroupCard,
  GroupCreate,
  GroupSummary,
  Interest,
  LikeResult,
  LikedUserCard,
  MatchCard,
  ProfileOwnResponse,
  ProfileUpdateRequest,
  RegistrationRequest,
  RegistrationResponse,
  RequestCard,
  RequestCreate,
  SkipResult,
  TelegramAuthRequest,
  TokenResponse,
  VoteResult,
} from '../types/api';

const p = (path: string): string => `${API_PREFIX}${path}`;

// --------------------------------------------------------------------- //
//  AUTH (auth.py)                                                       //
// --------------------------------------------------------------------- //
export const authApi = {
  /** initData → JWT + is_registered. Запрос без Bearer (его ещё нет). */
  telegram(body: TelegramAuthRequest): Promise<TokenResponse> {
    return request(p('/auth/telegram'), { method: 'POST', body, skipAuth: true });
  },
};

// --------------------------------------------------------------------- //
//  РЕГИСТРАЦИЯ (handoff_4; точка стыковки — см. CLAUDE_CODE_PROMPT)      //
// --------------------------------------------------------------------- //
export const registrationApi = {
  /** Создать User (анкета без фото; фото уже у бота в Redis). */
  register(body: RegistrationRequest): Promise<RegistrationResponse> {
    // skipAuth: на момент регистрации Bearer-токена ещё может не быть —
    // сервер авторизует по init_data внутри тела.
    return request(p('/registration'), { method: 'POST', body, skipAuth: true });
  },
};

// --------------------------------------------------------------------- //
//  ИНТЕРЕСЫ (эндпоинт добавляется на бэке — см. CLAUDE_CODE_PROMPT)      //
// --------------------------------------------------------------------- //
export const interestsApi = {
  /** Справочник интересов [{id, name}]. */
  list(): Promise<Interest[]> {
    return request(p('/interests'));
  },
};

// --------------------------------------------------------------------- //
//  ЛЕНТА (discovery.py)                                                 //
//  ВАЖНО: like/skip принимают параметры в QUERY, не в body.             //
// --------------------------------------------------------------------- //
export const discoveryApi = {
  /** Лента кандидатов. cursor — id последнего показанного (пагинация). */
  feed(cursor?: number, limit?: number): Promise<DiscoveryFeed> {
    return request(p('/discovery/feed'), { query: { cursor, limit } });
  },

  /** Лайк кандидата (query-параметр to_user_id). */
  like(toUserId: number): Promise<LikeResult> {
    return request(p('/discovery/like'), {
      method: 'POST',
      query: { to_user_id: toUserId },
    });
  },

  /** Скип кандидата (query-параметр skipped_user_id). */
  skip(skippedUserId: number): Promise<SkipResult> {
    return request(p('/discovery/skip'), {
      method: 'POST',
      query: { skipped_user_id: skippedUserId },
    });
  },
};

// --------------------------------------------------------------------- //
//  КОМПАНИИ + ГОЛОСОВАНИЕ (groups_router.py)                            //
// --------------------------------------------------------------------- //
export const groupsApi = {
  /** Мои компании (где состою как участник). Лёгкий список без состава. */
  listMine(): Promise<GroupSummary[]> {
    return request(p('/groups'));
  },

  /** Создать компанию из подтверждённого мэтча. */
  create(body: GroupCreate): Promise<GroupCard> {
    return request(p('/groups'), { method: 'POST', body });
  },

  /** Карточка компании + состав. */
  get(groupId: number): Promise<GroupCard> {
    return request(p(`/groups/${groupId}`));
  },

  /** Активные заявки компании (для голосующих). */
  listRequests(groupId: number): Promise<RequestCard[]> {
    return request(p(`/groups/${groupId}/requests`));
  },

  /** Подать заявку (join / invite / merge). */
  createRequest(groupId: number, body: RequestCreate): Promise<RequestCard> {
    return request(p(`/groups/${groupId}/requests`), { method: 'POST', body });
  },

  /** Статус заявки + прогресс голосования. */
  getRequest(requestId: number): Promise<RequestCard> {
    return request(p(`/requests/${requestId}`));
  },

  /** Проголосовать (query-параметр value=true|false). */
  vote(requestId: number, value: boolean): Promise<VoteResult> {
    return request(p(`/requests/${requestId}/vote`), {
      method: 'POST',
      query: { value },
    });
  },
};

// --------------------------------------------------------------------- //
//  ДОСТИЖЕНИЯ (модуль геймификации — GET /me/achievements)              //
// --------------------------------------------------------------------- //
export const achievementsApi = {
  /** Витрина достижений текущего пользователя (весь справочник + прогресс). */
  getMine(): Promise<AchievementsResponse> {
    return request(p('/me/achievements'));
  },
};

// --------------------------------------------------------------------- //
//  МАТЧИ (matches.py)                                                   //
// --------------------------------------------------------------------- //
export const matchesApi = {
  /** Все мэтчи текущего пользователя (свежие сверху). */
  list(): Promise<MatchCard[]> {
    return request(p('/matches'));
  },
};

// --------------------------------------------------------------------- //
//  ИСТОРИЯ ЛАЙКОВ (history.py)                                          //
// --------------------------------------------------------------------- //
export const historyApi = {
  /** Список лайкнутых текущим пользователем (свежие сверху). */
  list(): Promise<LikedUserCard[]> {
    return request(p('/history'));
  },

  /** Убрать лайк (мэтч, если был, НЕ удаляется — это отдельная сущность). */
  remove(targetUserId: number): Promise<void> {
    return request(p(`/history/${targetUserId}`), { method: 'DELETE' });
  },
};

// --------------------------------------------------------------------- //
//  ПРОФИЛЬ (profiles.py)                                                //
// --------------------------------------------------------------------- //
export const profileApi = {
  /** Свой полный профиль. */
  getMine(): Promise<ProfileOwnResponse> {
    return request(p('/me/profile'));
  },

  /** PATCH полей профиля. Передавать только то, что меняется. */
  updateMine(body: ProfileUpdateRequest): Promise<ProfileOwnResponse> {
    return request(p('/me/profile'), { method: 'PATCH', body });
  },
};

// --------------------------------------------------------------------- //
//  ФОТО-ПРОКСИ (эндпоинт добавляется на бэке — см. CLAUDE_CODE_PROMPT)   //
// --------------------------------------------------------------------- //
/**
 * URL картинки по Telegram file_id. Браузер не умеет рендерить file_id
 * напрямую, поэтому фронт указывает <img src> на прокси бэка, который
 * отдаёт байты через Bot API.
 *
 * Возвращаем строку URL (а не запрос), чтобы подставлять прямо в <img>.
 * Точка стыковки: путь /photo/{file_id} согласован в CLAUDE_CODE_PROMPT.
 */
export function photoUrl(fileId: string): string {
  return `${API_PREFIX}/photo/${encodeURIComponent(fileId)}`;
}
