/**
 * Обёртка над Telegram Mini App SDK (@telegram-apps/sdk-react v3).
 *
 * ЗАЧЕМ изолировать: весь остальной код не должен знать про конкретный SDK.
 * Если SDK сменится или появится React Native (где Telegram-окружения нет) —
 * меняется только этот файл. Наружу отдаём нейтральные функции.
 *
 * SDK v3 устроен как набор «компонентов» с методами .mount()/.isSupported().
 * initData приходит как сырая строка (retrieveRawInitData) — её и шлём на бэк.
 */
import {
  backButton,
  bindMiniAppCssVars,
  init,
  miniApp,
  retrieveRawInitData,
  viewport,
} from '@telegram-apps/sdk-react';

let initialized = false;
// Текущая отписка от onClick кнопки «Назад». Храним, чтобы старые
// обработчики не накапливались при переходах между экранами.
let backButtonOff: (() => void) | null = null;

/**
 * Инициализировать SDK один раз при старте приложения.
 *
 * Идемпотентно: повторный вызов ничего не делает. Часть mount-вызовов
 * обёрнута в try/catch и проверки isSupported — в старых клиентах Telegram
 * отдельные возможности отсутствуют, и это не должно ронять всё приложение.
 */
export function initTelegram(): void {
  if (initialized) return;
  initialized = true;

  // Поднимаем мост к Telegram. После этого доступны остальные компоненты.
  init();

  // Прокидываем тему Telegram в CSS-переменные (--tg-theme-*),
  // чтобы UI совпадал с нативным оформлением клиента пользователя.
  if (miniApp.mountSync.isAvailable()) {
    miniApp.mountSync();
    bindMiniAppCssVars();
  }

  // Вьюпорт: разворачиваем на всю высоту, чтобы экраны не «прыгали».
  if (viewport.mount.isAvailable()) {
    viewport
      .mount()
      .then(() => {
        if (viewport.expand.isAvailable()) viewport.expand();
      })
      .catch(() => {
        // не критично: если не смонтировался — просто работаем без fullscreen
      });
  }

  // Кнопку «назад» монтируем заранее; показ/скрытие — через setBackButton ниже.
  if (backButton.mount.isAvailable()) {
    backButton.mount();
  }

  // Сообщаем Telegram, что интерфейс готов (убирает экран загрузки клиента).
  if (miniApp.ready.isAvailable()) {
    miniApp.ready();
  }
}

/**
 * Сырая строка initData для отправки на бэк (/auth/telegram, /registration).
 *
 * Бэк сам валидирует подпись и достаёт telegram_id — фронт его не парсит.
 * Может вернуть undefined, если приложение открыто вне Telegram (например
 * в обычном браузере при разработке).
 */
export function getInitDataRaw(): string | undefined {
  try {
    return retrieveRawInitData();
  } catch {
    return undefined;
  }
}

/**
 * Управление нативной кнопкой «Назад» Telegram.
 * Экраны зовут setBackButton(handler) при входе и setBackButton(null) при выходе.
 */
export function setBackButton(onClick: (() => void) | null): void {
  if (!backButton.isMounted()) return;

  // Снимаем предыдущий обработчик, чтобы они не накапливались.
  if (backButtonOff) {
    backButtonOff();
    backButtonOff = null;
  }

  if (onClick) {
    backButton.show();
    // onClick возвращает функцию-отписку — сохраняем для следующего вызова.
    backButtonOff = backButton.onClick(onClick);
  } else {
    backButton.hide();
  }
}
