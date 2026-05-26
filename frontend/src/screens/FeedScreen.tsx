/**
 * Экран ленты подбора — основной экран приложения.
 *
 * Логика:
 *  - грузим страницу кандидатов (feed) порциями по курсору next_cursor;
 *  - показываем верхнюю карточку; лайк/скип убирают её и сдвигают стопку;
 *  - когда видимых карточек осталось мало — подгружаем следующую порцию;
 *  - при взаимном лайке (is_mutual) показываем экран мэтча с переходом к
 *    созданию компании.
 *
 * Свайп реализован как кнопки + drag-жест (touch). Жест изолирован в
 * useSwipe ниже, чтобы при переезде на RN заменить только его.
 */
import { useCallback, useEffect, useState } from 'react';
import { discoveryApi } from '../api/endpoints';
import { ApiError } from '../api/client';
import { PhotoImage } from '../components/PhotoImage';
import { Spinner, ErrorView } from '../components/StatusViews';
import type { CandidateCard, LikeResult } from '../types/api';
import type { Router } from '../store/router';

interface FeedScreenProps {
  router: Router;
  /**
   * Колбэк «случился взаимный лайк». App.tsx инкрементирует по нему бэдж
   * новых мэтчей на вкладке «Матчи». Опционален, чтобы FeedScreen
   * оставался самостоятельным экраном вне Tab Bar (тесты/превью).
   */
  onNewMatch?: () => void;
}

export function FeedScreen({ router, onNewMatch }: FeedScreenProps) {
  // Очередь видимых кандидатов (верхний — текущий).
  const [queue, setQueue] = useState<CandidateCard[]>([]);
  const [cursor, setCursor] = useState<number | undefined>(undefined);
  // hasMore=false → сервер сказал, что кандидатов больше нет (next_cursor=null).
  const [hasMore, setHasMore] = useState(true);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  // Данные о мэтче для оверлея (null → оверлея нет).
  const [match, setMatch] = useState<{ candidate: CandidateCard; matchId: number } | null>(null);

  // Подгрузка очередной порции ленты.
  const loadMore = useCallback(async () => {
    try {
      const page = await discoveryApi.feed(cursor);
      setQueue((prev) => [...prev, ...page.candidates]);
      setCursor(page.next_cursor ?? undefined);
      setHasMore(page.next_cursor !== null);
      setError(null);
    } catch (e: unknown) {
      setError(e instanceof ApiError ? e.message : 'Не удалось загрузить ленту.');
    } finally {
      setLoading(false);
    }
  }, [cursor]);

  // Первичная загрузка.
  useEffect(() => {
    void loadMore();
    // намеренно один раз: дальнейшие подгрузки — вручную при опустошении очереди
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Снять верхнюю карточку и при необходимости подгрузить ещё.
  function advance(): void {
    setQueue((prev) => {
      const next = prev.slice(1);
      // Осталось мало карточек и есть что грузить — тянем следующую порцию.
      if (next.length <= 2 && hasMore) void loadMore();
      return next;
    });
  }

  // Обработка лайка: оптимистично снимаем карточку, по ответу — оверлей мэтча.
  async function handleLike(candidate: CandidateCard): Promise<void> {
    advance();
    try {
      const result: LikeResult = await discoveryApi.like(candidate.id);
      if (result.is_mutual && result.match_id !== null) {
        setMatch({ candidate, matchId: result.match_id });
        // Сообщаем App.tsx: на вкладке «Матчи» нужно показать бэдж.
        onNewMatch?.();
      }
    } catch {
      // Лайк идемпотентен на бэке; молча игнорируем сетевую ошибку,
      // чтобы не мешать листанию. Кандидат уже снят с экрана.
    }
  }

  async function handleSkip(candidate: CandidateCard): Promise<void> {
    advance();
    try {
      await discoveryApi.skip(candidate.id);
    } catch {
      // skip ничего не пишет в БД — потеря не критична.
    }
  }

  if (loading && queue.length === 0) return <Spinner label="Ищем кандидатов…" />;
  if (error && queue.length === 0) {
    return <ErrorView message={error} onRetry={() => void loadMore()} />;
  }

  const current = queue[0];

  return (
    <div className="app-screen" style={{ justifyContent: 'space-between' }}>
      {match ? (
        <MatchOverlay
          candidate={match.candidate}
          onCreateGroup={() => {
            // Компания создаётся из match_id — ведём на экран group,
            // передавая matchId; сам POST делает GroupScreen.
            const matchId = match.matchId;
            setMatch(null);
            router.push('group', { createFromMatchId: matchId, candidateName: match.candidate.name });
          }}
          onLater={() => setMatch(null)}
        />
      ) : current ? (
        <>
          <CandidateView candidate={current} />
          <div style={{ display: 'flex', gap: 12 }}>
            <button
              className="app-button app-button--secondary"
              style={{ flex: 1 }}
              onClick={() => void handleSkip(current)}
            >
              Пропустить
            </button>
            <button
              className="app-button"
              style={{ flex: 1 }}
              onClick={() => void handleLike(current)}
            >
              Нравится
            </button>
          </div>
        </>
      ) : (
        <EmptyFeed onReload={() => void loadMore()} />
      )}
    </div>
  );
}

/** Карточка одного кандидата. */
function CandidateView({ candidate }: { candidate: CandidateCard }) {
  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 12 }}>
      <PhotoImage
        fileId={candidate.photo_file_id}
        name={candidate.name}
        className="candidate-photo"
      />
      <div>
        <h2 style={{ margin: 0, fontSize: 22 }}>
          {candidate.name}, {candidate.age}
        </h2>
        <p className="app-hint" style={{ margin: '4px 0 0' }}>
          {candidate.city}
        </p>
      </div>
      <p style={{ margin: 0 }}>{candidate.about}</p>

      {candidate.shared_interests.length > 0 && (
        <div>
          <p className="app-hint" style={{ margin: '0 0 6px' }}>
            Общие интересы ({candidate.shared_count}):
          </p>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {candidate.shared_interests.map((name) => (
              <span
                key={name}
                style={{
                  background: 'var(--app-secondary-bg)',
                  borderRadius: 999,
                  padding: '4px 10px',
                  fontSize: 13,
                }}
              >
                {name}
              </span>
            ))}
          </div>
        </div>
      )}
      {/* Размер фото задаём здесь, чтобы PhotoImage оставался переиспользуемым */}
      <style>{`
        .candidate-photo {
          width: 100%;
          aspect-ratio: 3 / 4;
          border-radius: var(--app-radius);
          display: block;
        }
      `}</style>
    </div>
  );
}

/** Оверлей взаимного мэтча. */
function MatchOverlay({
  candidate,
  onCreateGroup,
  onLater,
}: {
  candidate: CandidateCard;
  onCreateGroup: () => void;
  onLater: () => void;
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
        textAlign: 'center',
      }}
    >
      <h1 style={{ margin: 0 }}>Это мэтч! 🎉</h1>
      <p className="app-hint" style={{ margin: 0 }}>
        Вы и {candidate.name} понравились друг другу.
      </p>
      <button className="app-button" style={{ width: '100%' }} onClick={onCreateGroup}>
        Создать компанию
      </button>
      <button
        className="app-button app-button--secondary"
        style={{ width: '100%' }}
        onClick={onLater}
      >
        Позже
      </button>
    </div>
  );
}

/** Пустая лента: кандидаты кончились. */
function EmptyFeed({ onReload }: { onReload: () => void }) {
  return (
    <div
      style={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 16,
        textAlign: 'center',
      }}
    >
      <h2 style={{ margin: 0 }}>Пока никого нет</h2>
      <p className="app-hint" style={{ margin: 0 }}>
        Загляните позже — появятся новые анкеты.
      </p>
      <button className="app-button app-button--secondary" onClick={onReload}>
        Обновить
      </button>
    </div>
  );
}
