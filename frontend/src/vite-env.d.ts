/// <reference types="vite/client" />

// Типы переменных окружения Vite, используемых фронтом.
interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string;
}
interface ImportMeta {
  readonly env: ImportMetaEnv;
}
