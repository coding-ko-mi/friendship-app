/**
 * Контракты бэкенда — единый источник правды для фронта.
 *
 * ЗАЧЕМ отдельный файл: бэкенд напрямую мы не трогаем, поэтому формы
 * запросов/ответов держим в одном месте. Любое расхождение с API
 * правится здесь — и компилятор сразу покажет, где фронт "поедет".
 *
 * Каждое поле сверено с реальными файлами бэкенда:
 *   auth.py, discovery.py, schemas_matching.py, groups_schemas.py,
 *   groups_router.py, user.py, а также handoff_4 (регистрация).
 */

// ===================================================================== //
//  АВТОРИЗАЦИЯ                                                          //
//  Источник: app/api/v1/auth.py, schemas/auth.py                       //
// ===================================================================== //

/** Тело POST /api/v1/auth/telegram. Фронт шлёт сырую строку initData. */
export interface TelegramAuthRequest {
  init_data: string;
}

/**
 * Ответ /auth/telegram и /auth/refresh.
 *
 * is_registered=false → пользователь открыл Mini App, но ещё не прошёл
 * регистрацию (нет строки User). Фронт ведёт его в онбординг.
 *
 * ВНИМАНИЕ (точка стыковки): точные имена полей TokenResponse не видны
 * в knowledge (schemas/auth.py отсутствует). Поля ниже — ожидаемые по
 * смыслу auth.py. Если на бэке поля называются иначе (например
 * access_token vs accessToken) — правится ТОЛЬКО здесь.
 */
export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string; // обычно "bearer"
  is_registered: boolean;
}

/** Тело POST /api/v1/auth/refresh. */
export interface RefreshRequest {
  refresh_token: string;
}

// ===================================================================== //
//  РЕГИСТРАЦИЯ (гибрид: фото уже у бота, фронт шлёт остальное)          //
//  Источник: git_status_handoff_4.md (файл схемы в knowledge            //
//  отсутствует — это точка стыковки, см. CLAUDE_CODE_PROMPT).           //
// ===================================================================== //

/**
 * Тело POST /api/v1/registration.
 *
 * Фото в теле НЕТ — оно уже лежит в Redis на стороне сервера (бот принял).
 * telegram_id фронт НЕ передаёт — сервер берёт его из подписи init_data.
 * Интересы — только id из справочника, свободного ввода нет.
 *
 * ВНИМАНИЕ (точка стыковки): имена полей (init_data, interest_ids)
 * взяты из handoff. Файл schemas/registration.py в knowledge отсутствует.
 * Сверить и при расхождении поправить ТОЛЬКО этот интерфейс.
 */
export interface RegistrationRequest {
  init_data: string;
  name: string;
  age: number;
  about: string;
  city: string;
  interest_ids: number[];
}

/**
 * Ответ POST /api/v1/registration.
 *
 * Бэк возвращает минимум: id созданного User и его name (см.
 * backend/app/schemas/registration.py:RegistrationResponse). Токены он
 * НЕ возвращает — после регистрации фронт делает отдельный /auth/telegram.
 *
 * Поля access_token/refresh_token оставлены опциональными на случай, если
 * бэк позже начнёт отдавать токены сразу: фронт умеет работать в обоих
 * случаях (см. OnboardingScreen). Если этого не случится — поля будут
 * всегда undefined и просто не сработают, что безопасно.
 */
export interface RegistrationResponse {
  id: number;
  name: string;
  access_token?: string;
  refresh_token?: string;
}

// ===================================================================== //
//  СПРАВОЧНИК ИНТЕРЕСОВ                                                  //
//  Источник: модель interest.py (id, name). Эндпоинта пока НЕТ —        //
//  добавляется на бэке (GET /api/v1/interests). См. CLAUDE_CODE_PROMPT. //
// ===================================================================== //

export interface Interest {
  id: number;
  name: string;
}

// ===================================================================== //
//  ЛЕНТА ПОДБОРА                                                         //
//  Источник: schemas_matching.py, discovery.py                          //
// ===================================================================== //

/** Карточка кандидата в ленте. Сверено со schemas_matching.CandidateCard. */
export interface CandidateCard {
  id: number;
  name: string;
  age: number;
  about: string;
  photo_file_id: string; // Telegram file_id, НЕ url — рендерим через фото-прокси
  city: string;
  shared_interests: string[]; // названия общих интересов
  shared_count: number;
}

/** Страница ленты. Сверено со schemas_matching.DiscoveryFeed. */
export interface DiscoveryFeed {
  candidates: CandidateCard[];
  next_cursor: number | null; // null → кандидатов больше нет
}

/**
 * Результат лайка. Сверено со schemas_matching.LikeResult.
 * is_mutual=true → создан мэтч, match_id заполнен.
 */
export interface LikeResult {
  is_mutual: boolean;
  match_id: number | null;
}

/** Результат скипа. Сверено со schemas_matching.SkipResult. */
export interface SkipResult {
  skipped_user_id: number;
}

// ===================================================================== //
//  КОМПАНИИ + ГОЛОСОВАНИЕ                                                //
//  Источник: groups_schemas.py, groups_router.py                        //
// ===================================================================== //

/** Тип заявки. Сверено с enums.RequestType (бэк отдаёт UPPERCASE-строки). */
export type RequestType = 'JOIN' | 'INVITE' | 'MERGE';

/** Статус заявки. Сверено с enums.RequestStatus. */
export type RequestStatus = 'PENDING' | 'VOTING' | 'ACCEPTED' | 'REJECTED';

/** Карточка участника компании. Сверено с GroupMemberCard. */
export interface GroupMemberCard {
  id: number;
  name: string;
  age: number;
  photo_file_id: string;
  city: string;
}

/** Компания + состав. Сверено с GroupCard. */
export interface GroupCard {
  id: number;
  name: string;
  telegram_chat_id: number | null;
  members: GroupMemberCard[];
  member_count: number;
}

/** Тело POST /api/v1/groups (создать компанию из мэтча). */
export interface GroupCreate {
  name: string;
  match_id: number;
}

/** Тело POST /api/v1/groups/{id}/requests. Ровно один subject. */
export interface RequestCreate {
  type: RequestType;
  subject_user_id?: number | null;
  subject_group_id?: number | null;
}

/** Прогресс голосования по одной компании. Сверено с VoteProgress. */
export interface VoteProgress {
  group_id: number;
  members_total: number;
  votes_yes: number;
  votes_no: number;
  threshold: number;
  passed: boolean;
}

/** Карточка заявки + прогресс. Сверено с RequestCard. */
export interface RequestCard {
  id: number;
  type: RequestType;
  status: RequestStatus;
  subject_user_id: number | null;
  subject_group_id: number | null;
  target_group_id: number;
  created_at: string; // ISO-строка (datetime сериализуется в строку)
  progress: VoteProgress[];
}

/** Результат голоса. Сверено с VoteResult. */
export interface VoteResult {
  request_id: number;
  status: RequestStatus;
  finalized: boolean;
  added_user_id: number | null;
}

// ===================================================================== //
//  ДОСТИЖЕНИЯ (модуль геймификации)                                      //
//  Источник: backend/app/schemas/achievements.py + GET /me/achievements //
// ===================================================================== //

/**
 * Карточка одного достижения для витрины Mini App.
 *
 * earned=true → у пользователя оно уже есть; earned_at — ISO-строка момента
 * выдачи. Для невыданных earned_at == null (frontend рисует «ещё не открыто»).
 */
export interface AchievementCard {
  code: string;
  name: string;
  description: string;
  earned: boolean;
  earned_at: string | null;
}

/**
 * Ответ GET /api/v1/me/achievements — весь справочник + прогресс пользователя.
 * earned_count / total нужны, чтобы фронт сразу нарисовал «3/8» без подсчёта.
 */
export interface AchievementsResponse {
  items: AchievementCard[];
  earned_count: number;
  total: number;
}

// ===================================================================== //
//  МАТЧИ (список взаимных лайков)                                       //
//  Источник: backend/app/api/v1/matches.py + schemas/matching.py        //
// ===================================================================== //

/** Карточка мэтча для экрана «Матчи». user_id — id СОБЕСЕДНИКА. */
export interface MatchCard {
  match_id: number;
  user_id: number;
  name: string;
  age: number;
  photo_file_id: string;
  matched_at: string; // ISO-строка
}

// ===================================================================== //
//  ИСТОРИЯ ЛАЙКОВ (экран «История»)                                     //
//  Источник: backend/app/api/v1/history.py                              //
// ===================================================================== //

/** Один лайкнутый пользователь. Скипы здесь НЕ показываем (живут в Redis). */
export interface LikedUserCard {
  target_user_id: number;
  name: string;
  age: number;
  photo_file_id: string;
  liked_at: string; // ISO-строка
}

// ===================================================================== //
//  КОМПАНИИ — ЛЁГКИЙ СПИСОК                                              //
// ===================================================================== //

/** Карточка компании для списка «мои компании» (без подгрузки состава). */
export interface GroupSummary {
  id: number;
  name: string;
  member_count: number;
}

// ===================================================================== //
//  ПРОФИЛЬ (экран «Профиль»)                                             //
//  Источник: backend/app/schemas/profile.py                              //
// ===================================================================== //

/** Интерес в составе профиля. */
export interface ProfileInterest {
  id: number;
  name: string;
}

/** Пол — из enum Gender на бэке (lowercase: 'male' | 'female' | 'other'). */
export type Gender = 'male' | 'female' | 'other';

/** Ответ GET /api/v1/me/profile (полные данные владельцу). */
export interface ProfileOwnResponse {
  user_id: number;
  // Поля User (правятся через бот или через PATCH с расширением).
  name: string;
  age: number;
  about: string;
  photo_file_id: string;
  city: string;
  // Поля Profile.
  display_name: string | null;
  gender: Gender | null;
  extra_photos: string[];
  is_visible: boolean;
  latitude: number | null;
  longitude: number | null;
  // Расширение: интересы пользователя.
  interests: ProfileInterest[];
}

/**
 * Тело PATCH /api/v1/me/profile.
 *
 * Все поля опциональны (PATCH-логика). interest_ids = [] очищает все
 * интересы; null/undefined — поле не трогаем.
 */
export interface ProfileUpdateRequest {
  display_name?: string | null;
  gender?: Gender | null;
  latitude?: number | null;
  longitude?: number | null;
  extra_photos_urls?: string[] | null;
  is_visible?: boolean | null;
  about?: string | null;
  interest_ids?: number[] | null;
}
