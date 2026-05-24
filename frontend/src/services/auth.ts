/**
 * Сервис авторизации — мост между Telegram и api-слоем.
 *
 * ЗАЧЕМ отдельный слой: клиент (client.ts) умеет хранить и слать токен, но
 * не знает, ОТКУДА он берётся. Telegram-сервис умеет давать initData, но не
 * знает про токены. authService связывает их: меняет initData на JWT и
 * настраивает перелогин при протухшей сессии.
 */
import { authApi } from '../api/endpoints';
import {
  clearTokens,
  setSessionExpiredHandler,
  setTokens,
} from '../api/client';
import { getInitDataRaw } from './telegram';

/** Ошибка: приложение открыто вне Telegram (нет initData). */
export class NoTelegramEnvError extends Error {
  constructor() {
    super('Откройте приложение через Telegram.');
    this.name = 'NoTelegramEnvError';
  }
}

/** Результат входа: зарегистрирован ли пользователь (иначе → онбординг). */
export interface AuthState {
  isRegistered: boolean;
}

/**
 * Авторизоваться по initData: получить JWT и положить в клиент.
 *
 * Возвращает is_registered, по которому бутстрап решает,
 * вести в онбординг или сразу в ленту.
 */
export async function authenticate(): Promise<AuthState> {
  const initData = getInitDataRaw();
  if (!initData) throw new NoTelegramEnvError();

  const tokens = await authApi.telegram({ init_data: initData });
  setTokens(tokens.access_token, tokens.refresh_token);
  return { isRegistered: tokens.is_registered };
}

/**
 * Настроить автоматический перелогин.
 *
 * Когда access+refresh оба протухли, client.ts зовёт этот обработчик:
 * заново меняем initData (он в Telegram всегда «свежий») на новый JWT.
 * Если и это не вышло — чистим токены, и следующий запрос отдаст ошибку,
 * которую покажет UI.
 */
export function setupAutoRelogin(): void {
  setSessionExpiredHandler(async () => {
    try {
      const initData = getInitDataRaw();
      if (!initData) {
        clearTokens();
        return;
      }
      const tokens = await authApi.telegram({ init_data: initData });
      setTokens(tokens.access_token, tokens.refresh_token);
    } catch {
      clearTokens();
    }
  });
}
