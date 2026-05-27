/**
 * Экран компании + голосование.
 *
 * Два режима входа (через params роутера):
 *  - createFromMatchId — пришли с мэтча: сначала создаём компанию из match_id
 *    (POST /groups), затем показываем её карточку;
 *  - groupId — открываем уже существующую компанию по id.
 *
 * На карточке: состав, активные заявки на изменение состава и голосование
 * (за/против). Прогресс берём из VoteProgress (порог 75%, считает бэк).
 */
import { useCallback, useEffect, useState } from 'react';
import { groupsApi } from '../api/endpoints';
import { ApiError } from '../api/client';
import { PhotoImage } from '../components/PhotoImage';
import { Spinner, ErrorView } from '../components/StatusViews';
import type { GroupCard, RequestCard } from '../types/api';
import type { Router } from '../store/router';

interface GroupScreenProps {
  router: Router;
  // Параметры экрана из роутера (см. ScreenState.params).
  params?: {
    groupId?: number;
    createFromMatchId?: number;
    candidateName?: string;
  };
}

// Человекочитаемые подписи типов заявок.
const REQUEST_TYPE_LABEL: Record<string, string> = {
  JOIN: 'Заявка на вступление',
  INVITE: 'Приглашение',
  MERGE: 'Слияние компаний',
};

export function GroupScreen({ router, params }: GroupScreenProps) {
  const [group, setGroup] = useState<GroupCard | null>(null);
  const [requests, setRequests] = useState<RequestCard[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  // Имя компании при создании из мэтча.
  const [newName, setNewName] = useState('');

  // Загрузить компанию + её заявки.
  const loadGroup = useCallback(async (groupId: number) => {
    try {
      const [card, reqs] = await Promise.all([
        groupsApi.get(groupId),
        groupsApi.listRequests(groupId),
      ]);
      setGroup(card);
      setRequests(reqs);
      setError(null);
    } catch (e: unknown) {
      setError(e instanceof ApiError ? e.message : 'Не удалось загрузить компанию.');
    } finally {
      setLoading(false);
    }
  }, []);

  // При входе: если есть groupId — грузим; если createFromMatchId — ждём ввода
  // названия (создание по кнопке ниже), показываем форму создания.
  useEffect(() => {
    if (params?.groupId) {
      void loadGroup(params.groupId);
    } else {
      // Режим создания: загрузка не нужна, показываем форму.
      setLoading(false);
    }
  }, [params?.groupId, loadGroup]);

  // Создать компанию из мэтча.
  async function handleCreate(): Promise<void> {
    if (params?.createFromMatchId === undefined) return;
    if (newName.trim().length === 0) {
      setError('Введите название компании.');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const card = await groupsApi.create({
        name: newName.trim(),
        match_id: params.createFromMatchId,
      });
      setGroup(card);
      // После создания подгружаем заявки (пока пусто, но единообразно).
      const reqs = await groupsApi.listRequests(card.id);
      setRequests(reqs);
    } catch (e: unknown) {
      // 409: бэк уже знает компанию с тем же человеком — показываем
      // понятное сообщение вместо общей ошибки.
      if (e instanceof ApiError && e.status === 409) {
        setError('У вас уже есть компания с этим человеком');
      } else {
        setError(e instanceof ApiError ? e.message : 'Не удалось создать компанию.');
      }
    } finally {
      setLoading(false);
    }
  }

  // Проголосовать по заявке и перезагрузить список (обновить прогресс/статус).
  async function handleVote(requestId: number, value: boolean): Promise<void> {
    try {
      await groupsApi.vote(requestId, value);
      if (group) {
        const reqs = await groupsApi.listRequests(group.id);
        setRequests(reqs);
      }
    } catch (e: unknown) {
      setError(e instanceof ApiError ? e.message : 'Не удалось проголосовать.');
    }
  }

  if (loading) return <Spinner label="Загружаем компанию…" />;

  // Режим создания (ещё нет group, но есть match_id).
  if (!group && params?.createFromMatchId !== undefined) {
    return (
      <div className="app-screen">
        <h1 style={{ margin: 0 }}>Новая компания</h1>
        <p className="app-hint" style={{ marginTop: -8 }}>
          Компания создаётся из вашего мэтча
          {params.candidateName ? ` с ${params.candidateName}` : ''}.
        </p>
        <input
          className="app-input"
          placeholder="Название компании"
          maxLength={128}
          value={newName}
          onChange={(e) => setNewName(e.target.value)}
        />
        {error && <span className="app-error">{error}</span>}
        <button className="app-button" onClick={handleCreate} style={{ marginTop: 'auto' }}>
          Создать
        </button>
      </div>
    );
  }

  if (error && !group) {
    return <ErrorView message={error} onRetry={() => router.back()} />;
  }
  if (!group) return <ErrorView message="Компания не найдена." onRetry={() => router.back()} />;

  return (
    <div className="app-screen">
      <h1 style={{ margin: 0 }}>{group.name}</h1>
      <p className="app-hint" style={{ marginTop: -8 }}>
        Участников: {group.member_count}
      </p>

      {/* Состав */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {group.members.map((member) => (
          <div key={member.id} style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <PhotoImage
              fileId={member.photo_file_id}
              name={member.name}
              className="member-avatar"
            />
            <div>
              <div style={{ fontWeight: 600 }}>
                {member.name}, {member.age}
              </div>
              <div className="app-hint" style={{ fontSize: 13 }}>
                {member.city}
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Заявки на изменение состава + голосование */}
      {requests.length > 0 && (
        <div>
          <h2 style={{ fontSize: 18, margin: '8px 0' }}>Заявки</h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {requests.map((req) => (
              <RequestRow key={req.id} request={req} onVote={handleVote} />
            ))}
          </div>
        </div>
      )}

      {error && <span className="app-error">{error}</span>}

      {/* keyframes/размеры аватара — локально, чтобы PhotoImage был общим */}
      <style>{`
        .member-avatar {
          width: 48px;
          height: 48px;
          border-radius: 50%;
          flex-shrink: 0;
        }
      `}</style>
    </div>
  );
}

/** Одна заявка с прогрессом голосования и кнопками за/против. */
function RequestRow({
  request,
  onVote,
}: {
  request: RequestCard;
  onVote: (requestId: number, value: boolean) => void;
}) {
  const isActive = request.status === 'VOTING' || request.status === 'PENDING';

  return (
    <div
      style={{
        background: 'var(--app-secondary-bg)',
        borderRadius: 'var(--app-radius)',
        padding: 14,
        display: 'flex',
        flexDirection: 'column',
        gap: 10,
      }}
    >
      <div style={{ fontWeight: 600 }}>
        {REQUEST_TYPE_LABEL[request.type] ?? request.type}
      </div>

      {/* Прогресс по каждой голосующей компании (для merge их две) */}
      {request.progress.map((p) => (
        <div key={p.group_id} className="app-hint" style={{ fontSize: 13 }}>
          За: {p.votes_yes}/{p.threshold} (из {p.members_total})
          {p.passed ? ' ✓' : ''}
        </div>
      ))}

      {isActive ? (
        <div style={{ display: 'flex', gap: 8 }}>
          <button
            className="app-button app-button--secondary"
            style={{ flex: 1, padding: '10px' }}
            onClick={() => onVote(request.id, false)}
          >
            Против
          </button>
          <button
            className="app-button"
            style={{ flex: 1, padding: '10px' }}
            onClick={() => onVote(request.id, true)}
          >
            За
          </button>
        </div>
      ) : (
        <div className="app-hint" style={{ fontSize: 13 }}>
          Статус: {request.status === 'ACCEPTED' ? 'принято' : 'отклонено'}
        </div>
      )}
    </div>
  );
}
