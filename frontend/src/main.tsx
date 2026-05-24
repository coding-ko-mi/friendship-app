/**
 * Точка входа React-приложения.
 * Монтирует App в #root, подключает глобальные стили.
 */
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { App } from './App';
import './index.css';

const rootElement = document.getElementById('root');
if (!rootElement) throw new Error('Не найден элемент #root');

createRoot(rootElement).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
