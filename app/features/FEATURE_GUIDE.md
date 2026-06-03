# Feature Development Guide

Этот проект использует feature-based архитектуру: каждая пользовательская
возможность живет в отдельной папке внутри `app/features/<feature_name>/`.
Новая фича должна быть самодостаточной: модели, репозитории, сервисы, Telegram
handlers, клавиатуры, схемы, форматирование и тесты лежат рядом по домену.

В качестве рабочих примеров смотри:

- `price_monitoring` - мониторинг цен облигаций, фоновые проверки, антиспам.
- `offer_warning` - уведомления об офертах, пользовательские настройки,
  DateTrigger-задачи.

## Базовая структура фичи

Минимальный шаблон:

```text
app/features/<feature_name>/
├── __init__.py
├── models.py
├── repository.py
├── service.py
├── handlers.py
├── keyboards.py
├── schemas.py
├── formatter.py
└── notifier.py
```

Добавляй файлы только когда они реально нужны:

- `t_invest.py` - если фича ходит в T-Invest API.
- `config.py` - если есть параметры политики, лимиты, дефолты.
- `enums.py` - если нужны enum-значения для callbacks, текстов, типов событий.
- `detector.py`, `parser.py`, `client.py`, `sink.py` - если есть отдельный
  чистый доменный алгоритм, внешний клиент или приемник данных.

Папка тестов должна повторять домен:

```text
tests/features/<feature_name>/
├── __init__.py
├── test_repository.py
├── test_service.py
├── test_handlers.py
├── test_keyboards.py
├── test_formatter.py
└── test_schemas.py
```

## Главный принцип слоев

Handlers не должны содержать бизнес-логику. Они только:

1. Принимают `Message` или `CallbackQuery`.
2. Валидируют пользовательский ввод.
3. Вызывают сервис или репозиторий.
4. Отдают пользователю текст и клавиатуру.
5. Логируют ошибку и показывают короткий fallback.

Бизнес-логика должна жить в `service.py`, чистые вычисления - в отдельных
функциях вроде `detector.py`, форматирование текста - в `formatter.py`,
отправка сообщений - в `notifier.py`, работа с БД - только в `repository.py`.

## Async-правила

Все операции, которые ходят во внешний мир, должны быть асинхронными:

- SQLAlchemy-запросы через `async with session_scope() as session`.
- T-Invest/MOEX/HTTP-клиенты через async API и async context manager.
- Telegram-отправка через методы `aiogram.Bot`.
- Scheduler entrypoints, которые вызывают async-сервисы.

Чистые функции без I/O оставляй синхронными. Например, детекторы, парсеры,
классификаторы и форматтеры проще тестировать как обычные функции.

## Модели и таблицы

SQLAlchemy-модели храни в `models.py`.

Правила:

- Наследуйся от `core.database.Base`.
- Указывай `__tablename__`.
- Используй `Mapped[...]` и `mapped_column(...)`.
- Для Telegram ID используй `BigInteger`.
- Для пользовательских настроек обычно нужен `telegram_id` с `unique=True`,
  `nullable=False`, `index=True`.
- Добавляй `created_at` и `updated_at`, если запись изменяется пользователем.
- Для часто фильтруемых полей добавляй `index=True`.
- Пиши короткий `__repr__`, полезный для логов.

Пример:

```python
class NewFeatureSettings(Base):
    """Настройки новой фичи пользователя."""

    __tablename__ = "new_feature_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(
        BigInteger,
        unique=True,
        nullable=False,
        index=True,
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        onupdate=func.now(),
        nullable=True,
    )
```

После добавления модели импортируй ее в `DatabaseManager.create_tables()` в
`app/core/database.py`, иначе `Base.metadata.create_all` не увидит таблицу.

## Репозитории

Репозитории храни в `repository.py`. Они отвечают только за БД и не должны
знать про Telegram, scheduler или внешние API.

Типовой набор для пользовательских настроек:

- `get(telegram_id: int) -> Settings | None`
- `get_or_create(telegram_id: int) -> Settings`
- `update(telegram_id: int, **fields: object) -> bool`
- `toggle_alerts(telegram_id: int) -> bool`
- `list_users_with_alerts_enabled(...) -> list[...]`

Правила:

- Каждый метод репозитория открывает свою сессию через `session_scope()`.
- После возврата ORM-объекта за пределы сессии делай `session.expunge(obj)`.
- После изменений вызывай `await session.commit()`.
- После создания и перед возвратом объекта делай `await session.refresh(obj)`.
- Логируй ошибку с контекстом: telegram_id, figi, account_id, action.
- Не глотай ошибки без причины. Для read/list методов допустимо вернуть
  `None` или `[]`, для write-методов лучше либо вернуть `False`, либо пробросить
  исключение, но подход должен быть единым внутри фичи.

## Схемы

В `schemas.py` храни объекты, которыми слои обмениваются между собой.

Используй:

- `dataclass(frozen=True, slots=True)` для внутренних immutable DTO.
- `Enum` для доменных типов.
- `CallbackData` из aiogram для структурированных callback-данных.

Если callback имеет несколько параметров, предпочитай `CallbackData`, как в
`offer_warning`. Простые одиночные строковые callbacks можно держать в enum,
как в `price_monitoring`, но не смешивай оба подхода внутри одной фичи без
необходимости.

## Сервисы

`service.py` - оркестратор фичи. Он склеивает репозитории, внешние клиенты,
чистые алгоритмы, notifier и scheduler entrypoints.

Хороший сервис:

- Не содержит SQL-запросов напрямую.
- Не форматирует длинные сообщения руками.
- Не строит Telegram-клавиатуры.
- Получает зависимости через конструктор, если сервис нужно удобно тестировать.
- Имеет classmethod entrypoint для scheduler, если scheduler вызывает класс
  напрямую.
- Обрабатывает ошибку одного пользователя так, чтобы не сорвать обработку всех.

Пример формы:

```python
class NewFeatureService:
    """Оркестратор новой фичи."""

    def __init__(
        self,
        bot: Bot,
        *,
        settings_repo: type[NewFeatureRepository] = NewFeatureRepository,
        notifier: NewFeatureNotifier | None = None,
    ) -> None:
        self._bot = bot
        self._settings_repo = settings_repo
        self._notifier = notifier or NewFeatureNotifier(bot)

    @classmethod
    async def run_scheduled(cls, bot: Bot) -> None:
        """Scheduler entrypoint."""
        await cls(bot).run()

    async def run(self) -> None:
        """Выполняет основную работу фичи."""
```

## Внешние API

Код внешних API держи отдельно от сервиса:

- `t_invest.py` - запросы к T-Invest, преобразование SDK-ответов в DTO.
- отдельный `client.py` - если клиент большой или не привязан к T-Invest.

Правила:

- Не передавай SDK-объекты глубоко по приложению, если можно превратить их в
  dataclass из `schemas.py`.
- В логах указывай `telegram_id`, но не пиши токены.
- Ошибка одного счета пользователя не должна ломать обработку остальных счетов.
- Все сетевые вызовы должны мокаться в unit-тестах.

## Handlers

Handlers храни в `handlers.py` или в более конкретном имени, если оно уже
сложилось в проекте (`price_alert_handlers.py`).

Правила:

- В каждом файле создай `router = Router()`.
- Импортируй router в `app/bot.py` и подключи через `dp.include_routers(...)`.
- Для настроек используй FSM: `StatesGroup`, `State`, `FSMContext`.
- Сначала валидируй ввод, затем вызывай репозиторий/сервис.
- После успешного сохранения очищай state через `await state.clear()`.
- Для callback-ответов всегда вызывай `await callback.answer(...)`.
- Тексты, которые становятся длинными или повторяются, выноси в formatter или
  отдельные функции.

## Keyboards

Клавиатуры храни в `keyboards.py`.

Правила:

- Функции клавиатур должны быть чистыми: получают параметры, возвращают
  `InlineKeyboardBuilder`.
- Callback-строки не собирай руками, если используется `CallbackData`.
- Тексты кнопок лучше держать в enum или константах, если они переиспользуются.
- Не ходи в БД и внешние API из `keyboards.py`.

## Formatter и notifier

`formatter.py` отвечает только за текст:

- принимает DTO или доменные объекты;
- возвращает строку или пару `(message, shown_items)`;
- не отправляет сообщения;
- не ходит в БД.

`notifier.py` отвечает за Telegram-отправку:

- принимает `Bot` через конструктор;
- вызывает `bot.send_message(...)`;
- выбирает `parse_mode`;
- логирует результат;
- при необходимости записывает факт отправки в репозиторий.

## Фоновые задачи

Фоновые задачи регистрируются в `app/bot.py` через `AsyncIOScheduler`.

Правила:

- Scheduler должен вызывать короткий classmethod сервиса.
- Вся логика задачи должна быть внутри сервиса.
- Для регулярных проверок используй `CronTrigger`.
- Для разовых уведомлений на конкретное время используй `DateTrigger`.
- У DateTrigger-задач задавай стабильный `id`, чтобы избежать дублей после
  рестарта.
- Время для пользовательских уведомлений считай в `Europe/Moscow`, если фича
  завязана на МСК.

## Экспорт из `__init__.py`

В `__init__.py` экспортируй только публичные классы, которые нужны другим
частям приложения:

```python
from .service import NewFeatureService

__all__ = ["NewFeatureService"]
```

Не экспортируй handlers, модели и внутренние DTO без необходимости.

## Подключение новой фичи

После создания папки фичи проверь:

1. Модели импортированы в `DatabaseManager.create_tables()`.
2. Router импортирован и подключен в `app/bot.py`.
3. Scheduler job добавлен в `app/bot.py`, если фича фоновая.
4. Публичный сервис экспортирован из `__init__.py`, если нужен снаружи.
5. Тесты добавлены в `tests/features/<feature_name>/`.
6. Внешний I/O в тестах замокан.
7. `uv run pytest tests/features/<feature_name>` проходит.

## Тестирование

Пиши тесты вместе с кодом фичи.

Что тестировать:

- `repository.py` - создание, обновление, списки, edge cases.
- `service.py` - happy path, пустые данные, отсутствие токена, ошибки одного
  пользователя, scheduler job registration.
- `handlers.py` - callback flow, FSM states, валидация ввода.
- `keyboards.py` - callback_data и состав кнопок.
- `formatter.py` - готовый текст, сортировка, лимиты, пустые списки.
- `schemas.py` - pack/unpack callback data, enum helpers.
- `t_invest.py` или внешние клиенты - только с моками.

Unit-тесты не должны ходить в реальные T-Invest, MOEX, Telegram, файловую
систему или production-БД.

## Чеклист новой фичи

Перед тем как считать фичу готовой:

- [ ] Есть понятный доменный каталог `app/features/<feature_name>/`.
- [ ] Handlers тонкие, бизнес-логика в сервисе.
- [ ] Все I/O-операции async.
- [ ] Таблицы описаны через SQLAlchemy-модели и импортированы в create_tables.
- [ ] Репозитории возвращают detached ORM-объекты или DTO.
- [ ] Внешние API изолированы от handlers.
- [ ] Formatter не отправляет сообщения.
- [ ] Notifier не содержит бизнес-правил.
- [ ] Scheduler вызывает сервис, а не набор разрозненных функций.
- [ ] Ошибка одного пользователя не ломает всю batch-обработку.
- [ ] Добавлены focused pytest-тесты.
- [ ] Пройдены `ruff` и тесты фичи.
