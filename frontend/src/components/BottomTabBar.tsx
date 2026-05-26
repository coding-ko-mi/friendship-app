/**
 * Нижний таб-бар Mini App: 5 вкладок (главная, матчи, история, достижения,
 * профиль).
 *
 * Поведение:
 *  - тап по табу = router.setRoot(...) → меняется корневой экран и сбрасывается
 *    overlay-стек (например, открытый GroupScreen);
 *  - активный таб подсвечивается цветом кнопки темы Telegram;
 *  - на вкладке «Матчи» рисуется красный бейдж с числом новых мэтчей;
 *  - таб-бар фиксирован внизу и поверх контента, безопасный отступ снизу
 *    учитывается через --app-safe-bottom.
 *
 * Стили — только через --tg-theme-* (см. index.css), без хардкода.
 */
import type { Router, ScreenName } from '../store/router';

interface TabDef {
  name: ScreenName;
  label: string;
  icon: string; // эмодзи — на MVP без SVG-иконок
}

// Порядок слева направо. Менять только тут — UI сам перестроится.
const TABS: TabDef[] = [
  { name: 'feed', label: 'Главная', icon: '🏠' },
  { name: 'matches', label: 'Матчи', icon: '💬' },
  { name: 'history', label: 'История', icon: '🕐' },
  { name: 'achievements', label: 'Достижения', icon: '🏆' },
  { name: 'profile', label: 'Профиль', icon: '👤' },
];

interface BottomTabBarProps {
  router: Router;
  /** Число новых мэтчей для бейджа на вкладке «Матчи». 0 → бейдж скрыт. */
  matchesBadge: number;
  /** Вызывается при тапе по вкладке «Матчи» — App.tsx обнуляет бейдж. */
  onTabPress?: (name: ScreenName) => void;
}

export function BottomTabBar({
  router,
  matchesBadge,
  onTabPress,
}: BottomTabBarProps) {
  const activeName = router.root.name;

  return (
    <nav className="app-tabbar" role="tablist">
      {TABS.map((tab) => {
        const active = tab.name === activeName;
        const showBadge = tab.name === 'matches' && matchesBadge > 0;
        return (
          <button
            key={tab.name}
            role="tab"
            aria-selected={active}
            className={`app-tabbar__btn${active ? ' is-active' : ''}`}
            onClick={() => {
              onTabPress?.(tab.name);
              // Идемпотентно: повторный тап по активной вкладке очистит overlay-стек
              // (например, вернёт на корень после открытого GroupScreen).
              router.setRoot(tab.name);
            }}
          >
            <span className="app-tabbar__icon" aria-hidden>
              {tab.icon}
              {showBadge && (
                <span className="app-tabbar__badge" aria-label="новые">
                  {matchesBadge > 99 ? '99+' : matchesBadge}
                </span>
              )}
            </span>
            <span className="app-tabbar__label">{tab.label}</span>
          </button>
        );
      })}

      {/* Локальные стили компонента, чтобы не плодить классы в index.css.
          Все цвета — через --tg-theme-*/--app-* переменные. */}
      <style>{`
        .app-tabbar {
          position: fixed;
          left: 0;
          right: 0;
          bottom: 0;
          z-index: 10;
          display: flex;
          align-items: stretch;
          justify-content: space-around;
          background: var(--app-bg);
          border-top: 1px solid var(--app-secondary-bg);
          padding-bottom: var(--app-safe-bottom);
        }
        .app-tabbar__btn {
          flex: 1;
          appearance: none;
          background: transparent;
          border: none;
          padding: 8px 4px 6px;
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 2px;
          color: var(--app-hint);
          cursor: pointer;
          font-size: 11px;
          transition: color 0.15s ease;
        }
        .app-tabbar__btn.is-active {
          color: var(--app-button);
        }
        .app-tabbar__btn:active {
          opacity: 0.7;
        }
        .app-tabbar__icon {
          position: relative;
          font-size: 22px;
          line-height: 1;
        }
        .app-tabbar__label {
          font-size: 11px;
          font-weight: 500;
        }
        .app-tabbar__badge {
          position: absolute;
          top: -6px;
          right: -10px;
          min-width: 16px;
          height: 16px;
          padding: 0 4px;
          border-radius: 8px;
          background: #e53935;
          color: #fff;
          font-size: 10px;
          font-weight: 700;
          line-height: 16px;
          text-align: center;
          box-shadow: 0 0 0 2px var(--app-bg);
        }
      `}</style>
    </nav>
  );
}

/**
 * Высота таб-бара (используется в App.tsx, чтобы добавить нижний padding
 * контенту и он не уезжал под бар).
 */
export const TAB_BAR_HEIGHT = 64;
