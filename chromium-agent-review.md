# Ревью репозитория `laneAlien/chromium_agent_v1`

> Django-приложение с Playwright и APScheduler для автоматизированного просмотра YouTube. Деплоится в Docker с Xvfb.

---

## 1. Сводка приоритетов

| Приоритет | Что | Где |
|---|---|---|
| 🔴 High | Django запускается в режиме `runserver` (dev-сервер) в продакшн-контейнере | `Dockerfile` |
| 🔴 High | `headless=False` в Playwright при Docker-деплое — требует Xvfb, ломается без дисплея | `youtube.py:run_youtube_flow()` |
| 🔴 High | `run_session` вызывается APScheduler напрямую через функцию без Django context | `scheduler.py:_schedule_session_job()` |
| 🔴 High | Отсутствует README — нет инструкций по установке, конфигурации, смыслу проекта | корень проекта |
| 🟠 Med | Планировщик стартует в `apps.py` через `AppConfig.ready()` — запускается при каждой manage.py команде | `apps.py` |
| 🟠 Med | `_scheduler` — глобальная переменная без thread-safety; повторный старт не защищён | `scheduler.py` |
| 🟠 Med | `sync_playwright()` используется в async-контексте Django — блокирует event loop | `youtube.py:run_youtube_flow()` |
| 🟠 Med | `PLAYWRIGHT_USER_DATA_DIR` по умолчанию `/tmp/playwright-user-data` — данные браузера теряются между запусками контейнера | `youtube.py` |
| 🟡 Low | `docker-compose.yml` отсутствует — нет переменной `PLAYWRIGHT_USER_DATA_DIR` в env | `docker-compose.yml` |
| 🟡 Low | `.gitkeep` в корне указывает на пустую начальную структуру репо, которая не убрана | корень проекта |
| 🟡 Low | `AgentSettings` singleton через `pk=1` — нестандартный паттерн без документации | `models.py` |
| 🟡 Low | `_build_session_summary()` в `services.py` не защищён от деления на ноль при пустых decisions | `services.py` |

---

## 2. Критические проблемы

### 2.1 Django dev-сервер в продакшне

**Файл:** `Dockerfile`

```dockerfile
CMD ["sh", "-c", "Xvfb :99 -screen 0 1366x768x24 & python manage.py runserver 0.0.0.0:8000"]
```

`runserver` — однопоточный, не предназначен для production. Не обрабатывает сигналы корректно, не перезапускает упавшие воркеры. Нужен `gunicorn` или `uvicorn`:

```dockerfile
CMD ["sh", "-c", "Xvfb :99 -screen 0 1366x768x24 & gunicorn app.wsgi:application --bind 0.0.0.0:8000 --workers 1"]
```

### 2.2 `headless=False` в контейнере

**Файл:** `youtube.py`, функция `run_youtube_flow()`

```python
context = playwright.chromium.launch_persistent_context(
    ...
    headless=False,  # ← требует дисплей
    ...
)
```

В контейнере нет настоящего дисплея. Xvfb запускается, но если он упадёт раньше, Playwright получит ошибку подключения. Рекомендуется использовать `headless=True` или добавить retry при падении Xvfb.

### 2.3 APScheduler без Django ORM context

**Файл:** `scheduler.py`

APScheduler вызывает `run_session` в фоновом потоке. Django ORM требует корректного управления соединениями в потоках. Без `django.db.close_old_connections()` возможны ошибки `OperationalError: connection already closed`. Добавить:

```python
from django.db import close_old_connections

def _run_session_wrapper(session_id: int) -> None:
    close_old_connections()
    run_session(session_id)
```

### 2.4 Планировщик запускается при любой manage.py команде

**Файл:** `apps.py`

```python
class AgentConfig(AppConfig):
    def ready(self):
        from .scheduler import start_scheduler
        start_scheduler()
```

`AppConfig.ready()` вызывается при любой команде: `migrate`, `collectstatic`, `shell`. Добавить проверку:

```python
import os

def ready(self):
    if os.environ.get("RUN_MAIN") == "true" or not os.environ.get("DJANGO_MANAGE_COMMAND"):
        from .scheduler import start_scheduler
        start_scheduler()
```

Или проверять через `sys.argv`.

---

## 3. Серьёзные замечания

### 3.1 `sync_playwright()` блокирует event loop

`run_youtube_flow` — синхронная функция, вызываемая из APScheduler-потока. Это допустимо, но если Django переведут на async (ASGI), это станет проблемой. Комментарий с предупреждением будет уместен.

### 3.2 Пользовательские данные браузера в `/tmp`

```python
user_data_dir = Path(os.getenv("PLAYWRIGHT_USER_DATA_DIR", "/tmp/playwright-user-data"))
```

При перезапуске контейнера `/tmp` очищается. Необходимо монтировать persistent volume и задавать `PLAYWRIGHT_USER_DATA_DIR` в `docker-compose.yml`:

```yaml
volumes:
  - playwright_data:/data/playwright-user-data
environment:
  - PLAYWRIGHT_USER_DATA_DIR=/data/playwright-user-data
```

### 3.3 Отсутствие `docker-compose.yml`

В репозитории есть только `Dockerfile`, но нет `docker-compose.yml`. Для автономного деплоя необходим файл с базой данных (PostgreSQL), env-переменными и volume-конфигурацией.

---

## 4. Качество кода

### 4.1 Деление на ноль в `_build_session_summary`

```python
avg_duration = total_duration / len(decisions)  # если decisions пуст — ZeroDivisionError
```

Защитить:
```python
avg_duration = total_duration / len(decisions) if decisions else 0
```

### 4.2 `AgentSettings` singleton без документации

Паттерн `get_or_create(pk=1)` для singleton-конфигурации — нестандартный. Добавить комментарий в модель и ограничение на уровне `save()`:

```python
def save(self, *args, **kwargs):
    self.pk = 1
    super().save(*args, **kwargs)
```

### 4.3 Отсутствует README

Проект полностью лишён документации. Минимально необходимо:
- Что делает проект
- Как запустить (`docker build`, env-переменные)
- Как работает расписание
- Как добавить задачи YouTube (через Django admin?)

### 4.4 `.gitkeep` в корне

Служебный файл, оставшийся с инициализации репо. Удалить.

---

## 5. Положительные стороны

- Грамотное разделение на слои: `models`, `services`, `scheduler`, `youtube`
- `@transaction.atomic` в `run_session` — правильно
- Retry при ошибках Playwright с fallback-решением (пустой список кандидатов)
- Дедупликация видео по URL перед обработкой
- `misfire_grace_time=300` в APScheduler — корректная настройка для сессий

---

## 6. Чек-лист правок

- [ ] Заменить `runserver` на `gunicorn` в Dockerfile
- [ ] Изменить `headless=False` → `headless=True` или добавить fallback
- [ ] Добавить `close_old_connections()` в wrapper для APScheduler
- [ ] Защитить `start_scheduler()` от запуска при manage.py командах
- [ ] Создать `docker-compose.yml` с volume для данных браузера и БД
- [ ] Защитить от деления на ноль в `_build_session_summary`
- [ ] Написать README.md
- [ ] Удалить `.gitkeep`
- [ ] Добавить `save()` override для AgentSettings singleton
