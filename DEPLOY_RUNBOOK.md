# DEPLOY_RUNBOOK.md
# Деплой friendship-app на чистый VPS (Timeweb / Selectel, РФ)

> Цель: от чистого сервера до работающего бота и открывающегося Mini App.
> Время: ~1–2 часа при первом деплое.
> Требования: VPS 2 vCPU / 2 GB RAM, Ubuntu 22.04 LTS, домен с A-записью.

---

## 0. Перед началом — чеклист

- [ ] Есть домен (например `app.example.ru`), A-запись указывает на IP сервера
- [ ] Есть `TELEGRAM_BOT_TOKEN` (от @BotFather)
- [ ] Есть сгенерированный `JWT_SECRET` (команда ниже)
- [ ] Репозиторий с кодом доступен (GitHub или загрузка через scp)
- [ ] Знаешь пароль root или есть sudo-пользователь

---

## 1. Подключение и начальная настройка сервера

```bash
# Подключиться к серверу
ssh root@<IP_СЕРВЕРА>

# Обновить систему
apt update && apt upgrade -y

# Установить необходимые пакеты
apt install -y git curl ufw

# Настроить firewall: только SSH, HTTP, HTTPS
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable
ufw status  # должно показать активные правила
```

---

## 2. Установка Docker и Docker Compose

```bash
# Официальный скрипт установки Docker
curl -fsSL https://get.docker.com | sh

# Проверить установку
docker --version       # Docker 25+
docker compose version # Docker Compose 2.x

# Если нужно запускать docker без sudo (опционально)
usermod -aG docker $USER
# Переподключиться, чтобы группа применилась
```

---

## 3. Получение кода на сервер

```bash
# Вариант А: клонировать из Git (рекомендую)
cd /opt
git clone https://github.com/ВАШ_ЮЗЕ Р/friendship-app.git
cd friendship-app

# Вариант Б: загрузить архив с локальной машины
# (с локальной машины): scp -r ./friendship-app root@<IP>:/opt/
```

---

## 4. Сборка фронтенда

```bash
# На сервере устанавливаем Node.js (нужен только для сборки)
curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
apt install -y nodejs

# Собираем фронт
cd /opt/friendship-app/frontend

# Создаём .env для фронта (API URL должен быть твой домен)
cat > .env.production << 'EOF'
VITE_API_BASE_URL=https://ВАШ_ДОМЕН/api/v1
EOF

npm install
npm run build
# Должно создать frontend/dist/ — это статика, nginx её отдаёт

ls dist/  # убедись, что index.html появился

cd /opt/friendship-app
```

---

## 5. Настройка переменных окружения

```bash
cd /opt/friendship-app

# Копируем шаблон
cp .env.example .env

# Генерируем JWT_SECRET
openssl rand -hex 32
# Копируем вывод — вставим в .env

# Редактируем .env
nano .env
```

Заполнить в `.env` (остальные можно оставить дефолтными):

```env
POSTGRES_USER=friendship
POSTGRES_PASSWORD=<придумай_сложный_пароль>
POSTGRES_DB=friendship

DATABASE_URL=postgresql+asyncpg://friendship:<POSTGRES_PASSWORD>@postgres:5432/friendship
REDIS_URL=redis://redis:6379/0

JWT_SECRET=<вывод openssl rand -hex 32>

TELEGRAM_BOT_TOKEN=<токен от BotFather>

MINI_APP_URL=https://ВАШ_ДОМЕН/
WEBHOOK_URL=https://ВАШ_ДОМЕН/webhook
WEBHOOK_PATH=/webhook
WEBHOOK_HOST=0.0.0.0
WEBHOOK_PORT=8080
```

```bash
# Проверяем, что .env заполнен и не пустой
grep -E "^(POSTGRES_PASSWORD|JWT_SECRET|TELEGRAM_BOT_TOKEN|WEBHOOK_URL)=" .env
# Все 4 строки должны иметь значения (не пустые)
```

---

## 6. Настройка nginx конфига

```bash
# Заменяем YOUR_DOMAIN на реальный домен во всех местах
sed -i 's/YOUR_DOMAIN/ВАШ_ДОМЕН/g' nginx/nginx.conf

# Проверяем, что замена прошла
grep "server_name" nginx/nginx.conf
# Должно показать: server_name ВАШ_ДОМЕН;
```

---

## 7. Получение TLS-сертификата (Let's Encrypt)

**Важно:** A-запись домена должна уже указывать на IP сервера, иначе certbot не пройдёт проверку.

```bash
cd /opt/friendship-app

# Сначала поднимаем только nginx (без HTTPS) для ACME-challenge.
# Временно: закомментируем SSL-директивы и оставим только :80
# Быстрый способ — поднять certbot через standalone (временно занимает :80):

# Устанавливаем certbot
apt install -y certbot

# Получаем сертификат (certbot займёт порт 80 на несколько секунд)
# ВАШ_EMAIL — для уведомлений о продлении
certbot certonly --standalone \
  -d ВАШ_ДОМЕН \
  --email ВАШ_EMAIL \
  --agree-tos \
  --non-interactive

# Сертификаты появятся в /etc/letsencrypt/live/ВАШ_ДОМЕН/
ls /etc/letsencrypt/live/ВАШ_ДОМЕН/
# fullchain.pem  privkey.pem  cert.pem  chain.pem

# Копируем сертификаты в volume (docker-compose использует именованный volume)
# Проще: монтируем /etc/letsencrypt напрямую
```

**Обновляем docker-compose.yml** — заменяем volume certbot_certs на прямой bind-mount:

```bash
# В файле docker-compose.yml находим строку:
#   - certbot_certs:/etc/letsencrypt:ro
# И заменяем на:
#   - /etc/letsencrypt:/etc/letsencrypt:ro

sed -i 's|certbot_certs:/etc/letsencrypt:ro|/etc/letsencrypt:/etc/letsencrypt:ro|g' docker-compose.yml

# Аналогично для webroot (он нам теперь не нужен, nginx сам отдаёт .well-known)
# Строку certbot_webroot можно убрать или оставить.
```

**Настраиваем auto-renewal через cron:**

```bash
# Добавляем cron-задачу: обновлять каждые 60 дней + перезагружать nginx
crontab -e
# Добавить строку:
# 0 3 1 */2 * certbot renew --quiet && docker compose -f /opt/friendship-app/docker-compose.yml exec nginx nginx -s reload
```

---

## 8. Первый запуск стека

```bash
cd /opt/friendship-app

# Делаем entrypoint.sh исполняемым
chmod +x backend/entrypoint.sh

# Собираем образы (первый раз ~3-5 минут)
docker compose build

# Запускаем всё (PostgreSQL + Redis + API + бот + nginx)
docker compose up -d

# Следим за логами API (миграции + seed должны пройти)
docker compose logs -f api
```

Ожидаемый вывод API при первом старте:
```
==> [1/4] Ожидание PostgreSQL...
  PostgreSQL готов.
==> [2/4] Применение миграций (alembic upgrade head)...
  Миграции применены.
==> [3/4] Seed справочников...
Добавлено интересов: 22
Добавлено достижений: 8
  Seed завершён.
==> [4/4] Запуск API (uvicorn)...
INFO:     Application startup complete.
```

---

## 9. Проверка здоровья

```bash
# 1. Проверить статус всех контейнеров
docker compose ps
# Все сервисы должны быть: Up (healthy) или Up

# 2. Health check API
curl https://ВАШ_ДОМЕН/health
# Ожидаемый ответ: {"status":"ok"}

# 3. Проверить справочник интересов (новый эндпоинт B2)
curl https://ВАШ_ДОМЕН/api/v1/interests | python3 -m json.tool
# Должен вернуть массив из 22 интересов

# 4. Проверить достижения (требует JWT, но проверим что эндпоинт доступен)
curl -s -o /dev/null -w "%{http_code}" https://ВАШ_ДОМЕН/api/v1/me/achievements
# Ожидаем 401 (не 404!) — значит роутер подключён

# 5. Проверить что группы доступны
curl -s -o /dev/null -w "%{http_code}" https://ВАШ_ДОМЕН/api/v1/groups
# Ожидаем 401 или 422 — значит роутер подключён, не 404

# 6. Проверить бот — логи
docker compose logs bot
# Должно быть: "Webhook зарегистрирован: https://ВАШ_ДОМЕН/webhook"

# 7. Проверить Mini App в Telegram
# Открыть бота в Telegram → /start → должен открыться Mini App
```

---

## 10. Управление сервисом

```bash
# Остановить всё
docker compose down

# Перезапустить один сервис (например после правки кода)
docker compose up -d --build api

# Посмотреть логи
docker compose logs -f          # все сервисы
docker compose logs -f api      # только API
docker compose logs -f bot      # только бот
docker compose logs -f nginx    # только nginx

# Войти в контейнер для отладки
docker compose exec api bash
docker compose exec postgres psql -U friendship -d friendship

# Ручной запуск seed (если нужно повторно)
docker compose exec api python -m app.scripts.seed_interests
docker compose exec api python -m app.scripts.seed_achievements

# Посмотреть размер БД
docker compose exec postgres psql -U friendship -d friendship -c "\dt+"
```

---

## 11. Бэкап данных (обязательно перед любым обновлением)

```bash
# Дамп БД в файл с датой
docker compose exec postgres pg_dump -U friendship friendship > \
  /opt/backups/friendship_$(date +%Y%m%d_%H%M).sql

# Создать папку для бэкапов
mkdir -p /opt/backups

# Добавить в cron (ежедневный бэкап в 4:00)
crontab -e
# 0 4 * * * docker compose -f /opt/friendship-app/docker-compose.yml exec -T postgres \
#   pg_dump -U friendship friendship > /opt/backups/friendship_$(date +\%Y\%m\%d).sql

# Восстановление из дампа
docker compose exec -T postgres psql -U friendship friendship < /opt/backups/friendship_20260524.sql
```

---

## 12. Обновление кода (deploy after git push)

```bash
cd /opt/friendship-app

# Получить обновления
git pull

# Пересобрать образы и перезапустить
docker compose up -d --build

# Проверить что всё поднялось
docker compose ps
curl https://ВАШ_ДОМЕН/health
```

---

## 13. Типичные ошибки и их фикс

### API не стартует: "connection refused" к PostgreSQL
```bash
# Смотрим статус postgres
docker compose ps postgres
# Смотрим healthcheck
docker compose logs postgres
# Обычно: postgres ещё не готов, подождать 30-60 секунд и docker compose up -d api
```

### Webhook не регистрируется: "WEBHOOK_URL не задан"
```bash
# Проверить .env
grep WEBHOOK_URL .env
# Должен быть: WEBHOOK_URL=https://ВАШ_ДОМЕН/webhook (не пустой)
```

### nginx: "ssl_certificate not found"
```bash
# Проверить что сертификат есть
ls /etc/letsencrypt/live/ВАШ_ДОМЕН/
# Если нет — повторить шаг 7 (certbot certonly ...)
```

### Mini App не открывается: "Not allowed by CORS" или "Mixed content"
```bash
# Проверить что MINI_APP_URL в .env начинается с https://
grep MINI_APP_URL .env
# И что nginx возвращает HTTPS (не HTTP)
curl -I https://ВАШ_ДОМЕН/
```

### Бот получает апдейты, но не отвечает
```bash
# Смотрим логи бота
docker compose logs bot
# Проверяем что Redis доступен
docker compose exec bot python -c "from app.redis_client import redis_client; import asyncio; asyncio.run(redis_client.ping())"
```

### "alembic: command not found" в entrypoint
```bash
# Alembic должен быть в requirements.txt
docker compose exec api pip show alembic
# Если нет — добавить alembic в requirements.txt и пересобрать
```

### Данные пропали после docker compose up --build
```bash
# Это случится если volume postgres_data был удалён.
# Проверить volumes:
docker volume ls | grep postgres_data
# Если удалён — данные не восстановить без бэкапа.
# Поэтому: ВСЕГДА делай бэкап перед docker compose down -v (флаг -v удаляет volumes!)
# docker compose down (без -v) — volumes НЕ удаляет.
```

---

## Итоговая проверка деплоя

После завершения всех шагов:

- [ ] `curl https://ВАШ_ДОМЕН/health` → `{"status":"ok"}`
- [ ] `curl https://ВАШ_ДОМЕН/api/v1/interests` → массив 22 элементов
- [ ] Telegram `/start` боту → открывается Mini App
- [ ] Регистрация проходит (фото → анкета → лента)
- [ ] Логи чистые (нет ERROR кроме известных)
- [ ] `docker compose ps` → все сервисы Up
