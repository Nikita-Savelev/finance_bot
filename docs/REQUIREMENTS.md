# finance_bot — требования и архитектура

**Продукт (MVP зафиксирован):** [OVERVIEW.md](OVERVIEW.md).  
Этот файл — техническая схема под MVP v3.

## Цель

1. Мультивалютные счета и операции (доход / расход / перевод).
2. Импорт таблиц → транзакции с категориями (сразу в БД + итог).
3. Ручной ввод и удаление.
4. Статистика за месяц / период.
5. Месячный текстовый отчёт со сводом в **USD**.
6. Курсы валют с автообновлением **раз в час**.

## Доступ

| Параметр | Решение |
|----------|---------|
| Пользователи | Любое число, sign_up из template |
| Изоляция | FK `user` на всех фин. сущностях |
| UI | Русский; Telegram + Django Admin |

## Стек

Django + Postgres + aiogram 3 + Docker Compose.  
Порты: admin **8002**, postgres **5434**.  
FX: HTTP-клиент к внешнему API (URL в `.env`), фоновая задача раз в час.

## Связь с finance_script

Не импортировать как пакет. Перенос в `bot/components/finance/`: загрузка таблиц, категории, сводки, позже PDF.

## UX (кратко)

- Меню: операция, удаление, импорт, счета, категории, статистика, отчёт.
- Импорт без превью; неизвестный формат → ошибка.
- Отчёт при открытии **пересобирается из БД**.
- Правки операции в боте нет (только delete).

## Доменная модель

```
Users 1──* Account
Users 1──* Category          # только user-owned
Users 1──* CategoryHide      # скрытые базовые у пользователя
Users 1──* ImportBatch
Users 1──* MonthlyReport
Account 1──* Transaction
Category 1──* Transaction
ImportBatch 1──* Transaction
CurrencyRate                 # глобальный справочник курсов к USD
```

### Account

`user`, `name`, `currency`, `bank_label?`, `country?`, `is_active`, `notes?`

### Category

| Поле | Описание |
|------|----------|
| `name` | Уникально в рамках scope |
| `kind` | `income` / `expense` / `transfer` |
| `is_system` | Базовая (сид) |
| `user` | `null` у базовых; иначе владелец |
| `is_active` | Для системных — глобально; пользовательские можно удалять |

**CategoryHide:** `(user, category)` — пользователь скрыл базовую категорию у себя.

Эффективный список = базовые без скрытых + категории пользователя.

Сид базовых — из правил `finance_script` (плоский список имён).

### Transaction

`user`, `account`, `category?`, `occurred_at`, `amount` (>0), `currency` (= счёт),  
`direction` (`income`/`expense`/`transfer`), `description`, `source` (`manual`/`import`/`pdf`),  
`import_batch?`, `external_id?`, `counterpart_account?`

Дедуп: `(user, external_id)` или хэш `(account, date, amount, description, source)`.

### ImportBatch

`user`, `account?`, `filename`, `format_hint?`, `status`, `error_message?`, `stats_json?`, `created_at`

### MonthlyReport

Кэш необязателен для корректности (отчёт считается live). Поля на будущее/оптимизацию:

`user`, `year`, `month`, `summary_json?`, `updated_at`  
Уникальность `(user, year, month)`.

### CurrencyRate

| Поле | Описание |
|------|----------|
| `quote` | Код валюты (RUB, GEL, …); base всегда USD |
| `rate` | Сколько `quote` за 1 USD **или** сколько USD за 1 quote — зафиксировать в коде один смысл (предпочтительно: **units of quote per 1 USD**, как в exchangerate API) |
| `fetched_at` | Время записи |
| `source` | Идентификатор провайдера |

Храним **последний снимок** по каждой `quote` (upsert раз в час). История курсов — не MVP.

Конвертация в USD: `amount_usd = amount_quote / rate` при схеме «quote per 1 USD».

### Фоновая задача FX

- Интервал: 1 час.
- Запрос: `GET {FX_API_URL}` с `base=USD` (по умолчанию `https://api.exchangerate.fun/latest?base=USD`).
- Успех → upsert `CurrencyRate`.
- Ошибка → loguru warning, старые курсы остаются.
- Реализация MVP: asyncio-задача в процессе `main_bot` или `management command` + отдельный сервис; выбрать более простой вариант при коде (предпочтительно цикл в боте при старте).

Переменные `.env`: `FX_API_URL`, опционально `FX_SYNC_INTERVAL_SEC=3600`.

## Модули кода

| Модуль | Путь |
|--------|------|
| Счета | `handlers/accounts.py` |
| Ручной ввод / удаление | `handlers/manual_entry.py` |
| Импорт | `handlers/import_files.py` |
| Категории | `handlers/categories.py` |
| Статистика | `handlers/statistics.py` |
| Отчёты | `handlers/monthly_reports.py`, `finance/reports.py` |
| Парсеры | `finance/parsers/` |
| Категоризация | `finance/categorizer.py` |
| FX | `finance/fx.py` + фоновый sync |
| Агрегации | `finance/aggregations.py` |
| Админка | `core/admin.py` |

## Парсер (MVP)

Вход: файл + опционально счёт.  
Выход: `ParsedTransaction[]`.  
Эвристики по заголовкам + профили известных банков позже.  
Не распознано → `ImportBatch.failed`.

## Этапы реализации

| # | Этап |
|---|------|
| 1 | Skeleton + docs — **сделано** |
| 2 | Продуктовая дока MVP — **сделано (v3)** |
| 3 | Модели + admin + сид категорий — **сделано** |
| 4 | FX sync (hourly) + конвертация в USD — **сделано** |
| 5 | Счета + ручной ввод / удаление — **сделано** |
| 6 | Категории в боте (список / add / hide-delete) — **сделано** |
| 7 | Статистика — **сделано** |
| 8 | Импорт таблиц v1 — **сделано** |
| 9 | Месячные отчёты (текст §5 OVERVIEW) — **сделано** |
| 10 | Профили MyCredo / PDF Т-Банк — адаптивный парсер дальше |

## Вне скоупа MVP

Превью импорта, ручные колонки, правка операций в боте, правка текста отчёта, смена базовой валюты, история курсов на дату, файлы отчёта, mailing-фичи, семейный бюджет, сайт.

## Ограничения для агента

- Не читать/коммитить `.env`
- Не менять `template/`, не ломать `finance_script/`
- Секреты только через окружение
- Коммиты — только по просьбе
