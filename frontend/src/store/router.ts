/**
 * Лёгкий стейт-роутер: навигация между экранами Mini App.
 *
 * ЗАЧЕМ свой, а не react-router: Mini App — это экраны, а не URL-маршруты.
 * Стек экранов в состоянии переносится на React Native один-в-один (там
 * тоже навигация стеком, без адресной строки). Веб-специфики здесь нет.
 *
 * Модель состояния: rootScreen + overlay-стек.
 *   • rootScreen — текущая «вкладка» Tab Bar (или экран бутстрапа: loading,
 *     onboarding, error). Меняется через setRoot/reset.
 *   • stack[] — overlay-стек ПОВЕРХ root (например, GroupScreen, открытый
 *     из «Матчи»). push/back работают со стеком; смена вкладки в Tab Bar
 *     очищает стек.
 *
 * Активный экран = верх стека, если стек непуст; иначе rootScreen.
 * canGoBack = stack.length > 0 (root всегда «снизу», от него не уходим назад).
 */
import { useCallback, useReducer } from 'react';

/** Все экраны приложения. Параметры экрана — в payload (см. ScreenState). */
export type ScreenName =
  | 'loading' // бутстрап: идёт авторизация
  | 'onboarding' // регистрация (анкета)
  | 'feed' // лента подбора (Tab Bar)
  | 'matches' // список мэтчей и компаний (Tab Bar)
  | 'history' // история лайков (Tab Bar)
  | 'achievements' // витрина достижений (Tab Bar)
  | 'profile' // профиль (Tab Bar)
  | 'group' // карточка компании + голосование (overlay)
  | 'error'; // фатальная ошибка (нет Telegram и т.п.)

/** Состояние одного экрана: имя + произвольные параметры. */
export interface ScreenState {
  name: ScreenName;
  // Параметры экрана (например {groupId} для 'group'). Узко типизируем
  // на стороне экранов, здесь держим открытым, чтобы роутер был общим.
  params?: Record<string, unknown>;
}

interface RouterState {
  root: ScreenState; // текущая вкладка / стартовый экран
  stack: ScreenState[]; // overlay-стек поверх root (может быть пуст)
}

type RouterAction =
  | { type: 'push'; screen: ScreenState }
  | { type: 'replace'; screen: ScreenState }
  | { type: 'back' }
  | { type: 'reset'; screen: ScreenState }
  | { type: 'setRoot'; screen: ScreenState };

function reducer(state: RouterState, action: RouterAction): RouterState {
  switch (action.type) {
    case 'push':
      return { ...state, stack: [...state.stack, action.screen] };
    case 'replace':
      // Если стек непуст — меняем верх стека, иначе меняем сам root.
      if (state.stack.length > 0) {
        return {
          ...state,
          stack: [...state.stack.slice(0, -1), action.screen],
        };
      }
      return { ...state, root: action.screen };
    case 'back':
      // Из стека снимаем верх; если стек уже пуст — остаёмся на root.
      return state.stack.length > 0
        ? { ...state, stack: state.stack.slice(0, -1) }
        : state;
    case 'reset':
      // Полный сброс: новый root, стек пуст.
      return { root: action.screen, stack: [] };
    case 'setRoot':
      // Смена вкладки Tab Bar: меняем root, стек очищаем (overlay-экраны,
      // открытые из старой вкладки, не должны переезжать на новую).
      return { root: action.screen, stack: [] };
    default:
      return state;
  }
}

/** Публичный API роутера, который получают экраны. */
export interface Router {
  current: ScreenState;
  /** Текущий root (вкладка) — нужен Tab Bar, чтобы подсветить активный таб. */
  root: ScreenState;
  canGoBack: boolean;
  push: (name: ScreenName, params?: Record<string, unknown>) => void;
  replace: (name: ScreenName, params?: Record<string, unknown>) => void;
  /** Полный сброс (бутстрап). Используется при первом входе и в onboarding. */
  reset: (name: ScreenName, params?: Record<string, unknown>) => void;
  /** Сменить вкладку (Tab Bar): новый root, overlay-стек очищается. */
  setRoot: (name: ScreenName, params?: Record<string, unknown>) => void;
  back: () => void;
}

/** Хук-роутер. initial — стартовый экран (обычно 'loading'). */
export function useRouter(initial: ScreenName): Router {
  const [state, dispatch] = useReducer(reducer, {
    root: { name: initial },
    stack: [],
  });

  const push = useCallback((name: ScreenName, params?: Record<string, unknown>) => {
    dispatch({ type: 'push', screen: { name, params } });
  }, []);

  const replace = useCallback((name: ScreenName, params?: Record<string, unknown>) => {
    dispatch({ type: 'replace', screen: { name, params } });
  }, []);

  const reset = useCallback((name: ScreenName, params?: Record<string, unknown>) => {
    dispatch({ type: 'reset', screen: { name, params } });
  }, []);

  const setRoot = useCallback((name: ScreenName, params?: Record<string, unknown>) => {
    dispatch({ type: 'setRoot', screen: { name, params } });
  }, []);

  const back = useCallback(() => dispatch({ type: 'back' }), []);

  const current =
    state.stack.length > 0 ? state.stack[state.stack.length - 1] : state.root;

  return {
    current,
    root: state.root,
    canGoBack: state.stack.length > 0,
    push,
    replace,
    reset,
    setRoot,
    back,
  };
}
