/**
 * Экран «Достижения» — витрина прогресса геймификации.
 *
 * Только просмотр. Источник: GET /api/v1/me/achievements (бэкенд уже готов).
 * Сначала идут полученные (earned), потом ещё не открытые (тусклые).
 * Никаких кнопок: задача экрана — мотивировать, а не выдавать награды.
 */
import { useCallback, useEffect, useState } from 'react';
import { achievementsApi } from '../api/endpoints';
import { ApiError } from '../api/client';
import { Spinner, ErrorView } from '../components/StatusViews';
import type { AchievementCard, AchievementsResponse } from '../types/api';

export function AchievementsScreen() {
  const [data, setData] = useState<AchievementsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const res = await achievementsApi.getMine();
      setData(res);
    } catch (e: unknown) {
      setError(
        e instanceof ApiError ? e.message : 'Не удалось загрузить достижения.',
      );
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  if (data === null && !error) return <Spinner label="Загружаем достижения…" />;
  if (error && data === null) {
    return <ErrorView message={error} onRetry={() => void load()} />;
  }

  // Сортируем: сначала earned, потом нет. Внутри каждой группы — порядок с
  // бэка (по коду). Стабильная сортировка — слайс + Array.prototype.sort.
  const items = [...data!.items].sort(
    (a, b) => Number(b.earned) - Number(a.earned),
  );

  return (
    <div className="app-screen">
      <h1 style={{ margin: 0, fontSize: 22 }}>Достижения</h1>
      <p className="app-hint" style={{ marginTop: -8 }}>
        {data!.earned_count} из {data!.total} достижений
      </p>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {items.map((it) => (
          <AchievementRow key={it.code} card={it} />
        ))}
      </div>
    </div>
  );
}

function AchievementRow({ card }: { card: AchievementCard }) {
  // Эмодзи-иконку берём из первого символа name (на MVP отдельного поля
  // в API нет; названия достижений на бэке оформлены так, что первый символ
  // — эмодзи или буква, оба варианта смотрятся уместно в круглой плашке).
  const icon = card.name.codePointAt(0)
    ? String.fromCodePoint(card.name.codePointAt(0)!)
    : '★';

  return (
    <div
      style={{
        background: 'var(--app-secondary-bg)',
        borderRadius: 'var(--app-radius)',
        padding: 14,
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        opacity: card.earned ? 1 : 0.4,
        // filter: greyscale у не открытых — усиливает «тусклость» без хардкода цвета.
        filter: card.earned ? 'none' : 'grayscale(0.6)',
        transition: 'opacity 0.15s ease',
      }}
    >
      <div
        style={{
          width: 48,
          height: 48,
          borderRadius: '50%',
          background: 'var(--app-bg)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: 24,
          flexShrink: 0,
        }}
        aria-hidden
      >
        {icon}
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontWeight: 600 }}>{card.name}</div>
        <div className="app-hint" style={{ fontSize: 13 }}>
          {card.description}
        </div>
        {card.earned && card.earned_at && (
          <div className="app-hint" style={{ fontSize: 12, marginTop: 2 }}>
            Получено: {formatEarnedAt(card.earned_at)}
          </div>
        )}
      </div>
    </div>
  );
}

function formatEarnedAt(iso: string): string {
  return new Date(iso).toLocaleDateString('ru', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  });
}
