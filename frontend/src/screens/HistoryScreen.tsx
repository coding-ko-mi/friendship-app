/**
 * Экран «История» — список лайкнутых пользователей.
 *
 * Скипы сейчас живут в Redis (TTL) и в БД не пишутся, поэтому в истории
 * только лайки. Это намеренно подчёркивается подзаголовком.
 *
 * Действие на карточке — «Убрать лайк»: DELETE /history/{target_user_id}.
 * После успеха строку удаляем из локального state (оптимистично, но с откатом
 * при ошибке). Связанный мэтч, если был, НЕ удаляется — это другая сущность.
 */
import { useCallback, useEffect, useState } from 'react';
import { historyApi } from '../api/endpoints';
import { ApiError } from '../api/client';
import { PhotoImage } from '../components/PhotoImage';
import { Spinner, ErrorView } from '../components/StatusViews';
import type { LikedUserCard } from '../types/api';

export function HistoryScreen() {
  const [items, setItems] = useState<LikedUserCard[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  // id пользователей, для которых идёт DELETE (блокируем повторное нажатие).
  const [removing, setRemoving] = useState<Set<number>>(new Set());

  const load = useCallback(async () => {
    setError(null);
    try {
      const data = await historyApi.list();
      setItems(data);
    } catch (e: unknown) {
      setError(e instanceof ApiError ? e.message : 'Не удалось загрузить историю.');
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function handleRemove(targetUserId: number): Promise<void> {
    if (removing.has(targetUserId)) return;
    setRemoving((prev) => new Set(prev).add(targetUserId));
    // Сохраняем предыдущий state на случай отката.
    const prev = items;
    setItems((cur) => cur?.filter((u) => u.target_user_id !== targetUserId) ?? cur);
    try {
      await historyApi.remove(targetUserId);
    } catch (e: unknown) {
      // Откат UI и сообщение пользователю.
      setItems(prev);
      setError(e instanceof ApiError ? e.message : 'Не удалось убрать лайк.');
    } finally {
      setRemoving((cur) => {
        const next = new Set(cur);
        next.delete(targetUserId);
        return next;
      });
    }
  }

  if (items === null && !error) return <Spinner label="Загружаем историю…" />;
  if (error && items === null) {
    return <ErrorView message={error} onRetry={() => void load()} />;
  }

  return (
    <div className="app-screen">
      <h1 style={{ margin: 0, fontSize: 22 }}>История лайков</h1>
      <p className="app-hint" style={{ marginTop: -8 }}>
        Кого вы лайкнули. Скипы здесь не показываются — они временные.
      </p>

      {error && (
        <span className="app-error" role="alert">
          {error}
        </span>
      )}

      {items && items.length === 0 ? (
        <div
          className="app-hint"
          style={{
            background: 'var(--app-secondary-bg)',
            borderRadius: 'var(--app-radius)',
            padding: 14,
            textAlign: 'center',
          }}
        >
          Здесь появятся профили, которые вы лайкнули.
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {items!.map((u) => (
            <LikedRow
              key={u.target_user_id}
              user={u}
              busy={removing.has(u.target_user_id)}
              onRemove={() => void handleRemove(u.target_user_id)}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function LikedRow({
  user,
  busy,
  onRemove,
}: {
  user: LikedUserCard;
  busy: boolean;
  onRemove: () => void;
}) {
  return (
    <div
      style={{
        background: 'var(--app-secondary-bg)',
        borderRadius: 'var(--app-radius)',
        padding: 12,
        display: 'flex',
        alignItems: 'center',
        gap: 12,
      }}
    >
      <PhotoImage
        fileId={user.photo_file_id}
        name={user.name}
        className="liked-avatar"
      />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontWeight: 600 }}>
          {user.name}, {user.age}
        </div>
        <div className="app-hint" style={{ fontSize: 13 }}>
          Лайк: {formatLikedAt(user.liked_at)}
        </div>
      </div>
      <button
        className="app-button app-button--secondary"
        style={{ padding: '8px 12px', fontSize: 13 }}
        disabled={busy}
        onClick={onRemove}
      >
        {busy ? '…' : '✕ Убрать'}
      </button>
      <style>{`
        .liked-avatar {
          width: 48px;
          height: 48px;
          border-radius: 50%;
          flex-shrink: 0;
        }
      `}</style>
    </div>
  );
}

function formatLikedAt(iso: string): string {
  const d = new Date(iso);
  const now = new Date();
  if (d.toDateString() === now.toDateString()) {
    return `сегодня`;
  }
  return d.toLocaleDateString('ru', { day: 'numeric', month: 'short' });
}
