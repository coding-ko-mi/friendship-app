/**
 * HTTP-клиент — единственное место, где фронт реально ходит в сеть.
 *
 * ЗАЧЕМ так:
 *  - токен живёт в памяти модуля (решение по сессии: не localStorage),
 *    добавляется в Authorization автоматически — компоненты о нём не знают;
 *  - 401 запускает один прозрачный refresh, затем повтор запроса; если и
 *    refresh не помог — зовём onSessionExpired (перелогин через initData);
 *  - доменные ошибки бэка (detail) превращаются в ApiError с message,
 *    чтобы экраны показывали человеку понятный текст, а не «500».
 *
 * Веб-специфика (fetch) изолирована здесь. При переезде на React Native
 * меняется только тело этого модуля — вызовы из endpoints.ts не трогаются.
 */
import { API_BASE_URL } from '../config';

/** Ошибка уровня API: несёт http-статус и человекочитаемый текст. */
export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

// --- Состояние сессии (в памяти, не переживает перезагрузку — это намеренно) ---
let accessToken: string | null = null;
let refreshToken: string | null = null;

/**
 * Колбэк «сессия истекла и восстановить не удалось».
 * Его ставит бутстрап приложения: там лежит логика перелогина через initData.
 * Так клиент не знает про Telegram SDK — слои не перепутаны.
 */
let onSessionExpired: (() => Promise<void>) | null = null;

/** Положить токены (после auth/telegram, refresh или registration). */
export function setTokens(access: string, refresh: string): void {
  accessToken = access;
  refreshToken = refresh;
}

/** Сбросить сессию (logout / фатальная ошибка авторизации). */
export function clearTokens(): void {
  accessToken = null;
  refreshToken = null;
}

/** Зарегистрировать обработчик протухшей сессии (ставит authService). */
export function setSessionExpiredHandler(handler: () => Promise<void>): void {
  onSessionExpired = handler;
}

/** Параметры одного запроса. */
interface RequestOptions {
  method?: 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE';
  /** Тело — сериализуется в JSON. */
  body?: unknown;
  /** Query-параметры. Важно: like/skip на бэке принимают именно query. */
  query?: Record<string, string | number | boolean | undefined>;
  /** Запрос без Authorization (нужно для самого auth/telegram). */
  skipAuth?: boolean;
  /** Внутренний флаг: это повтор после refresh, второй раз не рефрешим. */
  _isRetry?: boolean;
}

/** Собрать полный URL с query-строкой. */
function buildUrl(path: string, query?: RequestOptions['query']): string {
  const url = new URL(API_BASE_URL + path, window.location.origin);
  if (query) {
    for (const [key, value] of Object.entries(query)) {
      if (value !== undefined) url.searchParams.set(key, String(value));
    }
  }
  return url.toString();
}

/** Вытащить понятный текст ошибки из ответа FastAPI ({detail: ...}). */
async function extractErrorMessage(response: Response): Promise<string> {
  try {
    const data = await response.json();
    if (typeof data?.detail === 'string') return data.detail;
    // Ошибки валидации FastAPI приходят массивом — берём первое сообщение.
    if (Array.isArray(data?.detail) && data.detail[0]?.msg) {
      return String(data.detail[0].msg);
    }
  } catch {
    // тело не JSON — падаем на дефолт ниже
  }
  return `Ошибка запроса (${response.status})`;
}

/**
 * Базовый запрос. Возвращает распарсенный JSON типа T.
 * Бросает ApiError на любой не-2xx (после попытки refresh при 401).
 */
export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, query, skipAuth = false, _isRetry = false } = options;

  const headers: Record<string, string> = {};
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  if (!skipAuth && accessToken) headers['Authorization'] = `Bearer ${accessToken}`;

  const response = await fetch(buildUrl(path, query), {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  // --- Прозрачное обновление токена при 401 ---
  if (response.status === 401 && !skipAuth && !_isRetry) {
    const refreshed = await tryRefresh();
    if (refreshed) {
      // Повторяем исходный запрос один раз с новым токеном.
      return request<T>(path, { ...options, _isRetry: true });
    }
    // Refresh не помог — отдаём управление обработчику перелогина.
    if (onSessionExpired) await onSessionExpired();
    // После перелогина пробуем ещё раз (токен уже мог обновиться).
    return request<T>(path, { ...options, _isRetry: true });
  }

  if (!response.ok) {
    throw new ApiError(response.status, await extractErrorMessage(response));
  }

  // 204 No Content — тела нет.
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

/**
 * Попытка обновить access-токен по refresh-токену.
 * Возвращает true при успехе. Вынесена сюда, т.к. это часть транспортного
 * слоя (работа с токеном), а не бизнес-логики авторизации.
 */
async function tryRefresh(): Promise<boolean> {
  if (!refreshToken) return false;
  try {
    // Путь задан строкой намеренно: импорт endpoints.ts создал бы цикл
    // (endpoints → client → endpoints). Это единственное исключение —
    // все прочие пути живут в endpoints.ts.
    const data = await request<{
      access_token: string;
      refresh_token: string;
    }>('/api/v1/auth/refresh', {
      method: 'POST',
      body: { refresh_token: refreshToken },
      skipAuth: true,
    });
    setTokens(data.access_token, data.refresh_token);
    return true;
  } catch {
    clearTokens();
    return false;
  }
}
