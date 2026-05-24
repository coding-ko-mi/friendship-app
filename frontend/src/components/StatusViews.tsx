/**
 * Мелкие переиспользуемые UI-компоненты состояния (загрузка/ошибка).
 * Держим вместе, чтобы экраны не дублировали разметку этих состояний.
 */

/** Центрированный индикатор загрузки. */
export function Spinner({ label }: { label?: string }) {
  return (
    <div
      style={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 12,
      }}
    >
      <div
        style={{
          width: 32,
          height: 32,
          border: '3px solid var(--app-secondary-bg)',
          borderTopColor: 'var(--app-button)',
          borderRadius: '50%',
          animation: 'app-spin 0.8s linear infinite',
        }}
      />
      {label && <span className="app-hint">{label}</span>}
      {/* keyframes объявляем инлайн, чтобы компонент был самодостаточным */}
      <style>{`@keyframes app-spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}

/** Экран ошибки с опциональной кнопкой повтора. */
export function ErrorView({
  message,
  onRetry,
}: {
  message: string;
  onRetry?: () => void;
}) {
  return (
    <div
      style={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 16,
        padding: 24,
        textAlign: 'center',
      }}
    >
      <span className="app-error">{message}</span>
      {onRetry && (
        <button className="app-button" onClick={onRetry}>
          Повторить
        </button>
      )}
    </div>
  );
}
