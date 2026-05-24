/**
 * Фото пользователя по Telegram file_id.
 *
 * ЗАЧЕМ компонент: file_id нельзя вставить в <img> напрямую — нужен
 * прокси-эндпоинт бэка (photoUrl). Пока эндпоинт не добавлен ИЛИ если фото
 * не загрузилось, показываем заглушку с инициалом, а не «сломанную картинку».
 * Так лента не «разваливается» до появления фото-прокси на бэке.
 */
import { useState } from 'react';
import { photoUrl } from '../api/endpoints';

interface PhotoImageProps {
  fileId: string;
  /** Имя — для инициала в заглушке. */
  name: string;
  className?: string;
}

export function PhotoImage({ fileId, name, className }: PhotoImageProps) {
  // failed=true → прокси не отдал картинку, рисуем заглушку.
  const [failed, setFailed] = useState(false);

  if (failed || !fileId) {
    return (
      <div
        className={className}
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          background: 'var(--app-secondary-bg)',
          color: 'var(--app-hint)',
          fontSize: '48px',
          fontWeight: 700,
        }}
      >
        {name.charAt(0).toUpperCase()}
      </div>
    );
  }

  return (
    <img
      className={className}
      src={photoUrl(fileId)}
      alt={name}
      onError={() => setFailed(true)}
      style={{ objectFit: 'cover' }}
    />
  );
}
