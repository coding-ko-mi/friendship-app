/**
 * Конфигурация фронта.
 *
 * ЗАЧЕМ: все внешние параметры (адрес API) в одном месте, читаются из
 * переменных окружения Vite (.env). Никаких хардкодов по коду.
 */

/**
 * Базовый адрес API без хвостового слэша.
 * Задаётся в .env как VITE_API_BASE_URL (например https://api.example.com).
 * Дефолт для локальной разработки — same-origin /api проксируется бэком.
 */
export const API_BASE_URL: string =
  import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, '') ?? '';

/** Префикс версии API. Все эндпоинты висят на /api/v1 (см. main.py бэка). */
export const API_PREFIX = '/api/v1';
