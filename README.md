# MaxBot

Бот поддержки МСП Красноярского края на платформе [MAX](https://max.ru).

RAG-пайплайн работает на любых данных — достаточно положить свои файлы в нужные папки (см. ниже).

## Структура

```
bot.py              — точка входа, polling
bot_callbacks.py    — маршрутизация callback-кнопок
bot_commands.py     — обработка текстовых команд
bot_ui.py           — экраны и клавиатуры
bot_texts.py        — тексты разделов меню
bot_rag.py          — интеграция с RAG
bot_runtime.py      — логирование, дедупликация
button_stats.py     — вывод статистики 
DataFrame/          — RAG-пайплайн: индексация, поиск, генерация
```

## Требования

- Python 3.11
- Токен бота MAX (получить через `@MasterBot` в мессенджере MAX)
- [Ollama](https://ollama.com) с загруженной моделью (по умолчанию `qwen3:8b`)
- Qdrant (локальный embedded или сервер)

## Установка

```bash
conda create -n maxbot python=3.11
conda activate maxbot
pip install -r requirements.txt
pip install -r DataFrame/requirements.txt
```

## Своя база знаний

Модель работает с любыми данными. Положи файлы в `DataFrame/Library/`:

```
DataFrame/Library/
├── knowledge_base.csv   — таблица с мерами поддержки (CSV)
├── knowledge_base.xlsx  — исходный Excel (опционально)
└── *.pdf                — любые PDF-документы
```

Формат CSV — минимум два столбца: `Категория` и текст. Пример:

```
Категория,Наименование,Описание
Финансовая поддержка,Микрозайм,Займы до 5 млн руб. под льготный процент
```

После добавления файлов пересобери индекс:

```bash
conda activate maxbot
cd DataFrame
python scripts/build_index.py
```

## Настройка

Создай `.env` в корне проекта:

```env
MAX_BOT_TOKEN=твой_токен

OLLAMA_BASE_URL=http://localhost:11434
LLM_MODEL=qwen2.5:3b

QDRANT_COLLECTION=support_kb
EMBEDDING_MODEL=intfloat/multilingual-e5-large
RETRIEVE_TOP_K=10

# Decision layer (опционально)
DECISION_MIN_SCORE=0.35
DECISION_STRONG_SCORE=0.55

# Реранкер (опционально, требует загрузки модели ~120MB)
USE_RERANK=false
RERANK_MODEL=cross-encoder/mmarco-mMiniLMv2-L12-H384-v1
```

## Запуск

```bash
conda activate maxbot
cd D:\DS\MaxBot
python bot.py
```

## Команды бота

| Команда | Описание |
|---|---|
| `/start`, `/menu` | Открыть главное меню |
| `/chat` | Включить режим чат-бот |
| `/exit` | Выключить режим чат-бот |
| `/help` | Справка |
| `/sources` | Список источников |
| `/reindex` | Переиндексация Qdrant |
| `/addsource <путь> [имя]` | Добавить файл и переиндексировать |

## Тестирование RAG без токена

```bash
conda activate maxbot
cd D:\DS\MaxBot
python -m DataFrame chat
```
