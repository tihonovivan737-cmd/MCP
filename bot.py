import asyncio
import logging
import os

from maxapi import Bot, Dispatcher
from maxapi.client.default import DefaultConnectionProperties
from maxapi.types import BotAdded, BotStarted, CallbackButton, ChatTitleChanged, MessageCallback, MessageCreated, MessageEdited, UserAdded
from maxapi.utils.inline_keyboard import InlineKeyboardBuilder

from bot_callbacks import handle_callback_event
from bot_chat_state import ChatHistoryStore
from bot_commands import handle_message_event
from bot_runtime import is_duplicate_bot_started, setup_user_activity_file_logging, should_send_greeting
from bot_texts import GREETING_TEXT

logging.basicConfig(level=logging.INFO)
setup_user_activity_file_logging()

TOKEN = os.getenv("MAX_BOT_TOKEN", "")
if not TOKEN:
    raise SystemExit("MAX_BOT_TOKEN is not set")
bot = Bot(token=TOKEN, default_connection=DefaultConnectionProperties(skip_auto_headers=("Accept-Encoding",)))
bot.headers["Accept-Encoding"] = "gzip, deflate"
dp = Dispatcher()
_CHATBOT_ACTIVE_CHATS: set[int] = set()
_CHAT_HISTORIES: ChatHistoryStore = {}
_BACKGROUND_TASKS: set[asyncio.Task] = set()


async def send_in_chat(chat_id: int | None, user_id: int, *, text: str, attachments=None, format=None):
    if chat_id is not None:
        await bot.send_message(chat_id=chat_id, text=text, attachments=attachments, format=format)
    else:
        await bot.send_message(user_id=user_id, text=text, attachments=attachments, format=format)


async def upsert_message(message, chat_id: int | None, user_id: int, *, text: str, attachments=None, format=None):
    if message is not None:
        await message.edit(text=text, attachments=attachments, format=format)
    else:
        await send_in_chat(chat_id, user_id, text=text, attachments=attachments, format=format)


def _finalize_background_task(task: asyncio.Task) -> None:
    _BACKGROUND_TASKS.discard(task)
    try:
        task.result()
    except Exception:
        logging.exception("Background task failed")


def schedule_background_task(coro) -> asyncio.Task:
    task = asyncio.create_task(coro)
    _BACKGROUND_TASKS.add(task)
    task.add_done_callback(_finalize_background_task)
    return task


@dp.bot_started()
async def bot_started(event: BotStarted):
    if is_duplicate_bot_started(event.chat_id):
        return
    if not should_send_greeting(event.chat_id):
        return
    builder = InlineKeyboardBuilder()
    builder.row(CallbackButton(text="▶️ НАЧАТЬ", payload="start"))
    await bot.send_message(chat_id=event.chat_id, text=GREETING_TEXT, attachments=[builder.as_markup()])


@dp.message_callback()
async def message_callback(event: MessageCallback):
    await handle_callback_event(
        event,
        upsert_message=upsert_message,
        chatbot_active_chats=_CHATBOT_ACTIVE_CHATS,
        chat_histories=_CHAT_HISTORIES,
    )


@dp.message_created()
async def message_created(event: MessageCreated):
    await handle_message_event(
        event,
        send_in_chat=send_in_chat,
        upsert_message=upsert_message,
        chatbot_active_chats=_CHATBOT_ACTIVE_CHATS,
        chat_histories=_CHAT_HISTORIES,
        schedule_background_task=schedule_background_task,
    )


@dp.bot_added()
async def bot_added(event: BotAdded):
    if not event.chat:
        return
    await bot.send_message(chat_id=event.chat_id, text=f"Привет, чат {event.chat.title}!")


@dp.message_edited()
async def message_edited(event: MessageEdited):
    pass


@dp.chat_title_changed()
async def chat_title_changed(event: ChatTitleChanged):
    pass


@dp.user_added()
async def user_added(event: UserAdded):
    await bot.send_message(chat_id=event.chat_id, text=f"Добро пожаловать, {event.user.first_name}!")


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
