/**
 * Экран «Профиль» — просмотр и редактирование своих данных.
 *
 * Бэкенд: GET /me/profile (читать), PATCH /me/profile (обновлять). Схема
 * расширена: бэк теперь принимает about и interest_ids — Mini App пишет их
 * одним PATCH-ом одновременно с display_name/is_visible (см. profile_service).
 *
 * Поведение редактирования:
 *  - name, age, city — read-only (правятся через бот, отдельный канал);
 *  - photo — заглушка с инициалом + toast «смена фото через бот»
 *    (фото-прокси и эндпоинт загрузки фото пока не реализованы);
 *  - about — textarea, редактируется;
 *  - interests — список чипов, мультиселект из справочника /interests.
 *
 * Сохраняем только изменённые поля (diff с initial state). Это и UX-вежливо,
 * и снижает риск перезаписать чужое поле.
 */
import { useCallback, useEffect, useState } from 'react';
import { interestsApi, profileApi } from '../api/endpoints';
import { ApiError, clearTokens } from '../api/client';
import { Spinner, ErrorView } from '../components/StatusViews';
import type { Interest, ProfileOwnResponse } from '../types/api';

interface ProfileScreenProps {
  /**
   * Колбэк после удаления аккаунта. App.tsx сбрасывает роутер на онбординг.
   * Опционален, чтобы экран оставался самостоятельным (тесты/превью).
   */
  onAccountDeleted?: () => void;
}

export function ProfileScreen({ onAccountDeleted }: ProfileScreenProps = {}) {
  const [profile, setProfile] = useState<ProfileOwnResponse | null>(null);
  const [allInterests, setAllInterests] = useState<Interest[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  // --- Локальные состояния редактируемых полей (инициируются после загрузки) ---
  const [about, setAbout] = useState('');
  const [selectedInterestIds, setSelectedInterestIds] = useState<Set<number>>(
    new Set(),
  );

  // --- UI-состояния ---
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  // Модалка подтверждения удаления аккаунта.
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deleting, setDeleting] = useState(false);

  // Загрузка профиля + справочника интересов.
  const load = useCallback(async () => {
    setError(null);
    try {
      const [p, list] = await Promise.all([
        profileApi.getMine(),
        interestsApi.list(),
      ]);
      setProfile(p);
      setAllInterests(list);
      setAbout(p.about);
      setSelectedInterestIds(new Set(p.interests.map((i) => i.id)));
    } catch (e: unknown) {
      setError(e instanceof ApiError ? e.message : 'Не удалось загрузить профиль.');
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  // Краткий toast (исчезает сам). Простая реализация — без библиотек.
  const showToast = useCallback((text: string) => {
    setToast(text);
    window.setTimeout(() => setToast(null), 2500);
  }, []);

  function toggleInterest(id: number): void {
    setSelectedInterestIds((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }

  async function handleSave(): Promise<void> {
    if (!profile) return;
    if (about.trim().length === 0) {
      showToast('Поле «О себе» не может быть пустым.');
      return;
    }

    // Собираем PATCH-тело: только реально изменённые поля.
    const body: { about?: string; interest_ids?: number[] } = {};
    if (about.trim() !== profile.about) {
      body.about = about.trim();
    }
    const currentIds = new Set(profile.interests.map((i) => i.id));
    const sameInterests =
      currentIds.size === selectedInterestIds.size &&
      [...currentIds].every((id) => selectedInterestIds.has(id));
    if (!sameInterests) {
      body.interest_ids = Array.from(selectedInterestIds);
    }

    if (Object.keys(body).length === 0) {
      showToast('Ничего не изменилось.');
      return;
    }

    setSaving(true);
    try {
      const updated = await profileApi.updateMine(body);
      setProfile(updated);
      // Синхронизируем локальные state с тем, что вернул бэк (на случай
      // нормализации значений: пробелы и пр.).
      setAbout(updated.about);
      setSelectedInterestIds(new Set(updated.interests.map((i) => i.id)));
      showToast('Профиль обновлён');
    } catch (e: unknown) {
      showToast(
        e instanceof ApiError ? e.message : 'Не удалось сохранить.',
      );
    } finally {
      setSaving(false);
    }
  }

  async function handleDeleteAccount(): Promise<void> {
    setDeleting(true);
    try {
      await profileApi.deleteMine();
      clearTokens();
      onAccountDeleted?.();
    } catch (e: unknown) {
      showToast(e instanceof ApiError ? e.message : 'Не удалось удалить аккаунт.');
      setDeleting(false);
      setShowDeleteConfirm(false);
    }
  }

  if ((profile === null || allInterests === null) && !error) {
    return <Spinner label="Загружаем профиль…" />;
  }
  if (error && profile === null) {
    return <ErrorView message={error} onRetry={() => void load()} />;
  }

  return (
    <div className="app-screen">
      {/* --- Аватар-заглушка с инициалом --- */}
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8 }}>
        <div
          style={{
            width: 96,
            height: 96,
            borderRadius: '50%',
            background: 'var(--app-secondary-bg)',
            color: 'var(--app-hint)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: 40,
            fontWeight: 700,
          }}
          aria-hidden
        >
          {profile!.name.charAt(0).toUpperCase()}
        </div>
        <button
          className="app-button app-button--secondary"
          style={{ padding: '8px 14px', fontSize: 13 }}
          onClick={() => showToast('Смена фото доступна через бот')}
        >
          Изменить фото
        </button>
      </div>

      {/* --- Имя + возраст (read-only) --- */}
      <div style={{ textAlign: 'center' }}>
        <h1 style={{ margin: 0, fontSize: 22 }}>
          {profile!.name}, {profile!.age}
        </h1>
        <p className="app-hint" style={{ margin: '4px 0 0' }}>
          {profile!.city}
        </p>
      </div>

      {/* --- О себе (редактируется) --- */}
      <label style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        <span style={{ fontWeight: 600 }}>О себе</span>
        <textarea
          className="app-textarea"
          value={about}
          maxLength={2000}
          onChange={(e) => setAbout(e.target.value)}
        />
      </label>

      {/* --- Интересы (мультиселект) --- */}
      <div>
        <p style={{ margin: '0 0 8px', fontWeight: 600 }}>Интересы</p>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
          {allInterests!.map((it) => {
            const active = selectedInterestIds.has(it.id);
            return (
              <button
                key={it.id}
                onClick={() => toggleInterest(it.id)}
                style={{
                  border: 'none',
                  borderRadius: 999,
                  padding: '8px 14px',
                  fontSize: 14,
                  cursor: 'pointer',
                  background: active ? 'var(--app-button)' : 'var(--app-secondary-bg)',
                  color: active ? 'var(--app-button-text)' : 'var(--app-text)',
                  transition: 'background 0.15s ease',
                }}
              >
                {it.name}
              </button>
            );
          })}
        </div>
      </div>

      {/* --- Кнопка сохранения --- */}
      <button
        className="app-button"
        disabled={saving}
        onClick={() => void handleSave()}
        style={{ marginTop: 'auto' }}
      >
        {saving ? 'Сохраняем…' : 'Сохранить'}
      </button>

      {/* --- Удаление аккаунта (визуально отделено сверху линией) --- */}
      <div
        style={{
          marginTop: 16,
          paddingTop: 16,
          borderTop: '1px solid var(--app-secondary-bg)',
        }}
      >
        <button
          onClick={() => setShowDeleteConfirm(true)}
          style={{
            width: '100%',
            appearance: 'none',
            border: 'none',
            borderRadius: 'var(--app-radius)',
            padding: '14px 20px',
            fontSize: 16,
            fontWeight: 600,
            background: 'transparent',
            color: '#e53935',
            cursor: 'pointer',
          }}
        >
          Удалить аккаунт
        </button>
      </div>

      {/* --- Модалка подтверждения удаления --- */}
      {showDeleteConfirm && (
        <div
          role="dialog"
          aria-modal="true"
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0, 0, 0, 0.5)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: 16,
            zIndex: 30,
          }}
          onClick={() => !deleting && setShowDeleteConfirm(false)}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            style={{
              background: 'var(--app-bg)',
              borderRadius: 'var(--app-radius)',
              padding: 20,
              maxWidth: 360,
              width: '100%',
              display: 'flex',
              flexDirection: 'column',
              gap: 16,
            }}
          >
            <h2 style={{ margin: 0, fontSize: 18 }}>Удалить аккаунт?</h2>
            <p className="app-hint" style={{ margin: 0 }}>
              Это действие необратимо. Все ваши матчи и данные будут удалены.
            </p>
            <div style={{ display: 'flex', gap: 8 }}>
              <button
                className="app-button app-button--secondary"
                style={{ flex: 1 }}
                disabled={deleting}
                onClick={() => setShowDeleteConfirm(false)}
              >
                Отмена
              </button>
              <button
                disabled={deleting}
                onClick={() => void handleDeleteAccount()}
                style={{
                  flex: 1,
                  appearance: 'none',
                  border: 'none',
                  borderRadius: 'var(--app-radius)',
                  padding: '14px 20px',
                  fontSize: 16,
                  fontWeight: 600,
                  background: '#e53935',
                  color: '#fff',
                  cursor: deleting ? 'default' : 'pointer',
                  opacity: deleting ? 0.6 : 1,
                }}
              >
                {deleting ? 'Удаляем…' : 'Удалить'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* --- Тостовое сообщение --- */}
      {toast && (
        <div
          role="status"
          style={{
            position: 'fixed',
            left: '50%',
            // Поднимаем над Tab Bar (64px + safe area).
            bottom: 'calc(80px + var(--app-safe-bottom))',
            transform: 'translateX(-50%)',
            background: 'var(--app-text)',
            color: 'var(--app-bg)',
            padding: '10px 16px',
            borderRadius: 999,
            fontSize: 14,
            maxWidth: '90%',
            textAlign: 'center',
            boxShadow: '0 4px 12px rgba(0,0,0,0.2)',
            zIndex: 20,
          }}
        >
          {toast}
        </div>
      )}
    </div>
  );
}
