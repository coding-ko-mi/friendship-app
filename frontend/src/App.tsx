/**
 * Корневой компонент: бутстрап и рендер активного экрана.
 *
 * Поток старта:
 *  1. инициализируем Telegram SDK и авто-перелогин;
 *  2. меняем initData на JWT (authenticate);
 *  3. is_registered=false → онбординг, true → лента;
 *  4. нет Telegram-окружения → экран ошибки.
 *
 * Навигация — через стейт-роутер (store/router). Нативная кнопка «Назад»
 * Telegram синхронизируется с возможностью вернуться в стеке экранов.
 */
import { useEffect, useRef, useState } from 'react';
import { useRouter } from './store/router';
import { initTelegram, setBackButton } from './services/telegram';
import { authenticate, setupAutoRelogin, NoTelegramEnvError } from './services/auth';
import { ApiError } from './api/client';
import { OnboardingScreen } from './screens/OnboardingScreen';
import { FeedScreen } from './screens/FeedScreen';
import { GroupScreen } from './screens/GroupScreen';
import { Spinner, ErrorView } from './components/StatusViews';

export function App() {
  const router = useRouter('loading');
  const [bootError, setBootError] = useState<string | null>(null);
  // Защита от двойного бутстрапа в StrictMode (dev монтирует дважды).
  const bootStarted = useRef(false);

  // Бутстрап один раз при монтировании.
  useEffect(() => {
    if (bootStarted.current) return;
    bootStarted.current = true;

    initTelegram();
    setupAutoRelogin();

    authenticate()
      .then(({ isRegistered }) => {
        router.reset(isRegistered ? 'feed' : 'onboarding');
      })
      .catch((e: unknown) => {
        if (e instanceof NoTelegramEnvError) {
          setBootError(e.message);
        } else {
          setBootError(
            e instanceof ApiError ? e.message : 'Не удалось авторизоваться.',
          );
        }
        router.reset('error');
      });
    // router стабилен (useCallback внутри), линтер можно не тревожить
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Синхронизируем нативную кнопку «Назад» с состоянием стека.
  useEffect(() => {
    if (router.canGoBack) {
      setBackButton(() => router.back());
    } else {
      setBackButton(null);
    }
  }, [router.canGoBack, router.current.name, router]);

  // Рендер активного экрана.
  switch (router.current.name) {
    case 'loading':
      return <Spinner label="Загрузка…" />;
    case 'onboarding':
      return <OnboardingScreen router={router} />;
    case 'feed':
      return <FeedScreen router={router} />;
    case 'group':
      return (
        <GroupScreen
          router={router}
          params={router.current.params as never}
        />
      );
    case 'error':
      return <ErrorView message={bootError ?? 'Что-то пошло не так.'} />;
    default:
      return <ErrorView message="Неизвестный экран." />;
  }
}
