import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// База '/' — Mini App обычно раздаётся с корня домена (MINI_APP_URL).
// Если будете класть в подпапку — поменяйте base здесь.
export default defineConfig({
  plugins: [react()],
  server: { port: 5173 },
});
