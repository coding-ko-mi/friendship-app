/**
 * Экран онбординга — анкета регистрации (гибрид).
 *
 * Фото пользователь уже отправил боту (оно в Redis на сервере). Здесь
 * собираем ОСТАЛЬНОЕ: имя, возраст, «о себе», город, интересы (id из
 * справочника). Шлём POST /api/v1/registration вместе с initData —
 * сервер берёт telegram_id из подписи, фронт его не передаёт.
 *
 * Интересы выбираются ТОЛЬКО из справочника (id), свободного ввода нет —
 * иначе сломается мэтчинг по interest_id (требование бэка).
 */
import { useEffect, useState } from 'react';
import { interestsApi, registrationApi } from '../api/endpoints';
import { ApiError } from '../api/client';
import { setTokens } from '../api/client';
import { getInitDataRaw } from '../services/telegram';
import { authenticate } from '../services/auth';
import { Spinner, ErrorView } from '../components/StatusViews';
import type { Interest } from '../types/api';
import type { Router } from '../store/router';

// Границы возраста — из CHECK-ограничения БД (ck_user_age_range: 18..100).
const AGE_MIN = 18;
const AGE_MAX = 100;
const NAME_MAX = 64; // String(64) в схеме User
const ABOUT_MIN = 1; // about NOT NULL
const CITY_MAX = 64;

interface OnboardingScreenProps {
  router: Router;
}

export function OnboardingScreen({ router }: OnboardingScreenProps) {
  // Справочник интересов с бэка.
  const [interests, setInterests] = useState<Interest[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  // Поля анкеты.
  const [name, setName] = useState('');
  const [age, setAge] = useState('');
  const [about, setAbout] = useState('');
  const [city, setCity] = useState('');
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());

  // Состояние отправки.
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  // Грузим справочник интересов при входе на экран.
  useEffect(() => {
    let cancelled = false;
    interestsApi
      .list()
      .then((list) => {
        if (!cancelled) setInterests(list);
      })
      .catch((e: unknown) => {
        if (!cancelled) {
          setLoadError(
            e instanceof ApiError ? e.message : 'Не удалось загрузить интересы.',
          );
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // Переключить выбор интереса (toggle в множестве).
  function toggleInterest(id: number): void {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }

  // Валидация формы. Возвращает текст ошибки или null если всё ок.
  // Дублирует ограничения бэка, чтобы не гонять заведомо плохой запрос.
  function validate(): string | null {
    const trimmedName = name.trim();
    const ageNum = Number(age);
    if (trimmedName.length < 1 || trimmedName.length > NAME_MAX) {
      return 'Укажите имя.';
    }
    if (!Number.isInteger(ageNum) || ageNum < AGE_MIN || ageNum > AGE_MAX) {
      return `Возраст должен быть от ${AGE_MIN} до ${AGE_MAX}.`;
    }
    if (about.trim().length < ABOUT_MIN) {
      return 'Напишите пару слов о себе.';
    }
    if (city.trim().length < 1 || city.trim().length > CITY_MAX) {
      return 'Укажите город.';
    }
    if (selectedIds.size === 0) {
      return 'Выберите хотя бы один интерес.';
    }
    return null;
  }

  async function handleSubmit(): Promise<void> {
    const error = validate();
    if (error) {
      setSubmitError(error);
      return;
    }

    const initData = getInitDataRaw();
    if (!initData) {
      setSubmitError('Откройте приложение через Telegram.');
      return;
    }

    setSubmitting(true);
    setSubmitError(null);
    try {
      const result = await registrationApi.register({
        init_data: initData,
        name: name.trim(),
        age: Number(age),
        about: about.trim(),
        city: city.trim(),
        interest_ids: Array.from(selectedIds),
      });

      // Если регистрация сразу вернула токены — используем их.
      // Иначе авторизуемся отдельным запросом (теперь is_registered=true).
      if (result.access_token && result.refresh_token) {
        setTokens(result.access_token, result.refresh_token);
      } else {
        await authenticate();
      }

      // Переход в ленту необратим (в анкету назад не возвращаемся) → reset.
      router.reset('feed');
    } catch (e: unknown) {
      setSubmitError(
        e instanceof ApiError ? e.message : 'Не удалось зарегистрироваться.',
      );
    } finally {
      setSubmitting(false);
    }
  }

  if (loadError) {
    return <ErrorView message={loadError} onRetry={() => window.location.reload()} />;
  }
  if (!interests) {
    return <Spinner label="Загружаем анкету…" />;
  }

  return (
    <div className="app-screen">
      <h1 style={{ margin: 0, fontSize: 24 }}>Расскажите о себе</h1>
      <p className="app-hint" style={{ marginTop: -8 }}>
        Фото вы уже отправили боту. Осталось заполнить анкету.
      </p>

      <input
        className="app-input"
        placeholder="Имя"
        maxLength={NAME_MAX}
        value={name}
        onChange={(e) => setName(e.target.value)}
      />
      <input
        className="app-input"
        placeholder="Возраст"
        inputMode="numeric"
        value={age}
        onChange={(e) => setAge(e.target.value.replace(/\D/g, ''))}
      />
      <textarea
        className="app-textarea"
        placeholder="О себе"
        value={about}
        onChange={(e) => setAbout(e.target.value)}
      />
      <input
        className="app-input"
        placeholder="Город"
        maxLength={CITY_MAX}
        value={city}
        onChange={(e) => setCity(e.target.value)}
      />

      <div>
        <p style={{ margin: '0 0 8px', fontWeight: 600 }}>Интересы</p>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
          {interests.map((interest) => {
            const active = selectedIds.has(interest.id);
            return (
              <button
                key={interest.id}
                onClick={() => toggleInterest(interest.id)}
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
                {interest.name}
              </button>
            );
          })}
        </div>
      </div>

      {submitError && <span className="app-error">{submitError}</span>}

      <button
        className="app-button"
        disabled={submitting}
        onClick={handleSubmit}
        style={{ marginTop: 'auto' }}
      >
        {submitting ? 'Сохраняем…' : 'Готово'}
      </button>
    </div>
  );
}
