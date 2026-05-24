/**
 * Лёгкий стейт-роутер: навигация между экранами Mini App.
 *
 * ЗАЧЕМ свой, а не react-router: Mini App — это экраны, а не URL-маршруты.
 * Стек экранов в состоянии переносится на React Native один-в-один (там
 * тоже навигация стеком, без адресной строки). Веб-специфики здесь нет.
 *
 * Реализация — useReducer со стеком экранов: push кладёт экран наверх,
 * back снимает верхний, replace меняет текущий (для необратимых переходов
 * вроде «онбординг завершён → лента», куда возвращаться нельзя).
 */
import { useCallback, useReducer } from 'react';

/** Все экраны приложения. Параметры экрана — в payload (см. ScreenState). */
export type ScreenName =
  | 'loading' // бутстрап: идёт авторизация
  | 'onboarding' // регистрация (анкета)
  | 'feed' // лента подбора
  | 'group' // карточка компании + голосование
  | 'error'; // фатальная ошибка (нет Telegram и т.п.)

/** Состояние одного экрана: имя + произвольные параметры. */
export interface ScreenState {
  name: ScreenName;
  // Параметры экрана (например {groupId} для 'group'). Узко типизируем
  // на стороне экранов, здесь держим открытым, чтобы роутер был общим.
  params?: Record<string, unknown>;
}

interface RouterState {
  stack: ScreenState[]; // непустой стек; верхний элемент — активный экран
}

type RouterAction =
  | { type: 'push'; screen: ScreenState }
  | { type: 'replace'; screen: ScreenState }
  | { type: 'back' }
  | { type: 'reset'; screen: ScreenState };

function reducer(state: RouterState, action: RouterAction): RouterState {
  switch (action.type) {
    case 'push':
      return { stack: [...state.stack, action.screen] };
    case 'replace':
      return { stack: [...state.stack.slice(0, -1), action.screen] };
    case 'back':
      // Не даём опустошить стек: если экран один — остаёмся на нём.
      return state.stack.length > 1
        ? { stack: state.stack.slice(0, -1) }
        : state;
    case 'reset':
      return { stack: [action.screen] };
    default:
      return state;
  }
}

/** Публичный API роутера, который получают экраны. */
export interface Router {
  current: ScreenState;
  canGoBack: boolean;
  push: (name: ScreenName, params?: Record<string, unknown>) => void;
  replace: (name: ScreenName, params?: Record<string, unknown>) => void;
  reset: (name: ScreenName, params?: Record<string, unknown>) => void;
  back: () => void;
}

/** Хук-роутер. initial — стартовый экран (обычно 'loading'). */
export function useRouter(initial: ScreenName): Router {
  const [state, dispatch] = useReducer(reducer, { stack: [{ name: initial }] });

  const push = useCallback((name: ScreenName, params?: Record<string, unknown>) => {
    dispatch({ type: 'push', screen: { name, params } });
  }, []);

  const replace = useCallback((name: ScreenName, params?: Record<string, unknown>) => {
    dispatch({ type: 'replace', screen: { name, params } });
  }, []);

  const reset = useCallback((name: ScreenName, params?: Record<string, unknown>) => {
    dispatch({ type: 'reset', screen: { name, params } });
  }, []);

  const back = useCallback(() => dispatch({ type: 'back' }), []);

  return {
    current: state.stack[state.stack.length - 1],
    canGoBack: state.stack.length > 1,
    push,
    replace,
    reset,
    back,
  };
}
