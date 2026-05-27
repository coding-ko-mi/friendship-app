/**
 * Корневой компонент: бутстрап и рендер активного экрана.
 *
 * Поток старта:
 *  1. инициализируем Telegram SDK и авто-перелогин;
 *  2. меняем initData на JWT (authenticate);
 *  3. is_registered=false → онбординг, true → лента;
 *  4. нет Telegram-окружения → экран ошибки.
 *
 * Навигация — через стейт-роутер (store/router): rootScreen (вкладка
 * Tab Bar) + overlay-стек. Нативная кнопка «Назад» Telegram синхронизируется
 * со стеком (кнопка показывается, только если есть куда возвращаться).
 *
 * Tab Bar показываем только после успешной авторизации — не на экранах
 * loading/onboarding/error (там пользователь не «в приложении»).
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { useRouter, type ScreenName } from './store/router';
import { initTelegram, setBackButton } from './services/telegram';
import { authenticate, setupAutoRelogin, NoTelegramEnvError } from './services/auth';
import { ApiError } from './api/client';
import { OnboardingScreen } from './screens/OnboardingScreen';
import { FeedScreen } from './screens/FeedScreen';
import { GroupScreen } from './screens/GroupScreen';
import { MatchesScreen } from './screens/MatchesScreen';
import { HistoryScreen } from './screens/HistoryScreen';
import { AchievementsScreen } from './screens/AchievementsScreen';
import { ProfileScreen } from './screens/ProfileScreen';
import { BottomTabBar, TAB_BAR_HEIGHT } from './components/BottomTabBar';
import { Spinner, ErrorView } from './components/StatusViews';

/** Экраны, перед которыми Tab Bar не показываем (бутстрап-фазы). */
const NON_TAB_ROOTS: ReadonlySet<ScreenName> = new Set([
  'loading',
  'onboarding',
  'error',
]);

export function App() {
  const router = useRouter('loading');
  const [bootError, setBootError] = useState<string | null>(null);
  // Защита от двойного бутстрапа в StrictMode (dev монтирует дважды).
  const bootStarted = useRef(false);

  // Бэдж новых мэтчей: счётчик, который инкрементируется при is_mutual в ленте
  // и обнуляется при заходе на вкладку «Матчи».
  const [matchesBadge, setMatchesBadge] = useState(0);

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

  // Колбэк для FeedScreen: при is_mutual инкрементируем бэдж новых мэтчей.
  // Бэдж видит весь App, чтобы Tab Bar мог его показать на «Матчи».
  const handleNewMatch = useCallback(() => {
    setMatchesBadge((n) => n + 1);
  }, []);

  // Тап по табу: на «Матчи» — сбрасываем бэдж (пользователь увидит список).
  const handleTabPress = useCallback((name: ScreenName) => {
    if (name === 'matches') setMatchesBadge(0);
  }, []);

  // Решение: показывать ли Tab Bar. На loading/onboarding/error — НЕТ.
  const showTabBar = !NON_TAB_ROOTS.has(router.root.name);

  return (
    <>
      <div
        style={{
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          // Чтобы контент не уезжал под Tab Bar — добавляем нижний паддинг,
          // равный высоте бара ВМЕСТЕ с безопасной зоной (внутри бара тоже
          // есть padding-bottom: safe-bottom, поэтому суммируем).
          paddingBottom: showTabBar
            ? `calc(${TAB_BAR_HEIGHT}px + var(--app-safe-bottom))`
            : 0,
          minHeight: 0,
        }}
      >
        <ScreenSwitch
          router={router}
          bootError={bootError}
          onNewMatch={handleNewMatch}
        />
      </div>

      {showTabBar && (
        <BottomTabBar
          router={router}
          matchesBadge={matchesBadge}
          onTabPress={handleTabPress}
        />
      )}
    </>
  );
}

/**
 * Рендер активного экрана. Вынесено в подкомпонент, чтобы App.tsx читался
 * сверху вниз без громоздкого switch внутри JSX.
 */
function ScreenSwitch({
  router,
  bootError,
  onNewMatch,
}: {
  router: ReturnType<typeof useRouter>;
  bootError: string | null;
  onNewMatch: () => void;
}) {
  switch (router.current.name) {
    case 'loading':
      return <Spinner label="Загрузка…" />;
    case 'onboarding':
      return <OnboardingScreen router={router} />;
    case 'feed':
      return <FeedScreen router={router} onNewMatch={onNewMatch} />;
    case 'matches':
      return <MatchesScreen router={router} />;
    case 'history':
      return <HistoryScreen />;
    case 'achievements':
      return <AchievementsScreen />;
    case 'profile':
      return (
        <ProfileScreen
          onAccountDeleted={() => router.reset('onboarding')}
        />
      );
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
