/**
 * Экран «Матчи» — две секции в одном прокручиваемом списке:
 *  1. Компании пользователя (GET /groups). Тап → GroupScreen.
 *  2. Мэтчи (GET /matches). На MVP — просто список (тап пока без действия).
 *
 * При входе на экран бэдж новых мэтчей в Tab Bar сбрасывается (callback
 * onEnter из App.tsx).
 */
import { useCallback, useEffect, useState } from 'react';
import { groupsApi, matchesApi } from '../api/endpoints';
import { ApiError } from '../api/client';
import { Spinner, ErrorView } from '../components/StatusViews';
import { PhotoImage } from '../components/PhotoImage';
import type { GroupSummary, MatchCard } from '../types/api';
import type { Router } from '../store/router';

interface MatchesScreenProps {
  router: Router;
}

export function MatchesScreen({ router }: MatchesScreenProps) {
  const [groups, setGroups] = useState<GroupSummary[] | null>(null);
  const [matches, setMatches] = useState<MatchCard[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      // Параллельный запрос — оба ресурса независимы.
      const [g, m] = await Promise.all([
        groupsApi.listMine(),
        matchesApi.list(),
      ]);
      setGroups(g);
      setMatches(m);
    } catch (e: unknown) {
      setError(e instanceof ApiError ? e.message : 'Не удалось загрузить матчи.');
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  // Полный экран загрузки только при первом входе (когда обоих списков ещё нет).
  if (groups === null && matches === null && !error) {
    return <Spinner label="Загружаем…" />;
  }
  if (error && groups === null && matches === null) {
    return <ErrorView message={error} onRetry={() => void load()} />;
  }

  const hasGroups = (groups?.length ?? 0) > 0;
  const hasMatches = (matches?.length ?? 0) > 0;
  const isEmpty = !hasGroups && !hasMatches;

  return (
    <div className="app-screen">
      {/* --- Компании --- */}
      <SectionTitle>Компании</SectionTitle>
      {hasGroups ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {groups!.map((g) => (
            <GroupRow
              key={g.id}
              group={g}
              onOpen={() => router.push('group', { groupId: g.id })}
            />
          ))}
        </div>
      ) : (
        <EmptyHint text="Компаний пока нет. Создайте первую из мэтча." />
      )}

      {/* --- Мэтчи --- */}
      <SectionTitle>Матчи</SectionTitle>
      {hasMatches ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {matches!.map((m) => (
            <MatchRow key={m.match_id} match={m} />
          ))}
        </div>
      ) : (
        <EmptyHint text="Пока нет взаимных лайков. Полайкайте в ленте." />
      )}

      {/* Доп-подсказка, если ВСЁ пусто (новичок). */}
      {isEmpty && (
        <div className="app-hint" style={{ textAlign: 'center', marginTop: 8 }}>
          Начните с вкладки «Главная» — там лента кандидатов.
        </div>
      )}
    </div>
  );
}

/* ----- Вспомогательные кусочки UI ----- */

function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <h2 style={{ margin: '8px 0 0', fontSize: 18, fontWeight: 700 }}>
      {children}
    </h2>
  );
}

function EmptyHint({ text }: { text: string }) {
  return (
    <div
      className="app-hint"
      style={{
        background: 'var(--app-secondary-bg)',
        borderRadius: 'var(--app-radius)',
        padding: 14,
        textAlign: 'center',
      }}
    >
      {text}
    </div>
  );
}

function GroupRow({
  group,
  onOpen,
}: {
  group: GroupSummary;
  onOpen: () => void;
}) {
  return (
    <button
      onClick={onOpen}
      style={{
        appearance: 'none',
        border: 'none',
        background: 'var(--app-secondary-bg)',
        borderRadius: 'var(--app-radius)',
        padding: 14,
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        cursor: 'pointer',
        textAlign: 'left',
        color: 'var(--app-text)',
      }}
    >
      <div
        style={{
          width: 44,
          height: 44,
          borderRadius: 12,
          background: 'var(--app-button)',
          color: 'var(--app-button-text)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: 20,
          flexShrink: 0,
        }}
        aria-hidden
      >
        👥
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div
          style={{
            fontWeight: 600,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
        >
          {group.name}
        </div>
        <div className="app-hint" style={{ fontSize: 13 }}>
          Участников: {group.member_count}
        </div>
      </div>
      <span aria-hidden style={{ color: 'var(--app-hint)' }}>
        ›
      </span>
    </button>
  );
}

function MatchRow({ match }: { match: MatchCard }) {
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
        fileId={match.photo_file_id}
        name={match.name}
        className="match-avatar"
      />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontWeight: 600 }}>
          {match.name}, {match.age}
        </div>
        <div className="app-hint" style={{ fontSize: 13 }}>
          {formatMatchedAt(match.matched_at)}
        </div>
      </div>
      <style>{`
        .match-avatar {
          width: 48px;
          height: 48px;
          border-radius: 50%;
          flex-shrink: 0;
        }
      `}</style>
    </div>
  );
}

/**
 * «Сегодня» / «Вчера» / дата — лёгкое форматирование без зависимостей.
 * Локаль ru — основная аудитория продукта.
 */
function formatMatchedAt(iso: string): string {
  const d = new Date(iso);
  const now = new Date();
  const isToday = d.toDateString() === now.toDateString();
  if (isToday) {
    return `Сегодня в ${d.getHours().toString().padStart(2, '0')}:${d
      .getMinutes()
      .toString()
      .padStart(2, '0')}`;
  }
  const yesterday = new Date(now);
  yesterday.setDate(now.getDate() - 1);
  if (d.toDateString() === yesterday.toDateString()) return 'Вчера';
  return d.toLocaleDateString('ru', {
    day: 'numeric',
    month: 'short',
  });
}
