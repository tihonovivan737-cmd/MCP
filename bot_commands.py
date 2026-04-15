"""Обработка текстовых команд и сообщений."""

from __future__ import annotations

import asyncio
import os

from bot_chat_state import ChatHistoryStore, conversation_key, get_chat_history, reset_chat_state
from bot_rag import add_source_and_reindex, answer_from_dataframe_async, list_sources_from_postgres, reindex_from_postgres
from bot_runtime import log_user_activity
from bot_ui import chat_dialog_keyboard, send_main_menu

CHAT_HISTORY_TURNS = max(1, int(os.environ.get("CHAT_HISTORY_TURNS", "6")))


def _history_safe_answer(answer: str) -> str:
    return answer.split("\n\nИсточники:\n", maxsplit=1)[0].strip()


async def handle_message_event(
    event,
    *,
    send_in_chat,
    upsert_message,
    chatbot_active_chats: set[int],
    chat_histories: ChatHistoryStore,
    schedule_background_task,
) -> None:
    if event.message.sender and event.message.sender.is_bot:
        return
    text = event.message.body.text if event.message.body else None
    if not text:
        return

    chat_id, user_id = event.get_ids()
    log_user_activity(action="message_created", user=event.message.sender, chat_id=chat_id)
    cmd = text.strip()
    cmd_lower = cmd.lower()

    if cmd_lower in ("/start", "/menu"):
        reset_chat_state(chatbot_active_chats, chat_histories, chat_id=chat_id, user_id=user_id)
        await send_main_menu(upsert_message, None, chat_id, user_id or 0)
        return
    if cmd_lower == "/chat":
        if chat_id is not None:
            chatbot_active_chats.add(chat_id)
        await send_in_chat(
            chat_id=chat_id,
            user_id=user_id or 0,
            text="Режим Чат-бот включен.\n\nЗадайте свой вопрос.",
            attachments=[chat_dialog_keyboard()],
        )
        return
    if cmd_lower == "/exit":
        reset_chat_state(chatbot_active_chats, chat_histories, chat_id=chat_id, user_id=user_id)
        await send_in_chat(chat_id=chat_id, user_id=user_id or 0, text="Режим Чат-бот выключен.")
        return
    if cmd_lower == "/help":
        await send_in_chat(
            chat_id=chat_id,
            user_id=user_id or 0,
            text=(
                "Доступные команды:\n"
                "/start — открыть стартовое меню\n"
                "/menu — открыть главное меню\n"
                "/chat — включить режим Чат-бот\n"
                "/exit — выключить режим Чат-бот\n"
                "/help — показать эту справку\n"
                "/sources — список источников в PostgreSQL\n"
                "/reindex — переиндексация Qdrant из PostgreSQL\n"
                "/addsource <путь_к_файлу> [логическое_имя] — добавить файл в PostgreSQL и переиндексировать"
            ),
        )
        return
    if cmd_lower == "/sources":
        await send_in_chat(chat_id=chat_id, user_id=user_id or 0, text=await asyncio.to_thread(list_sources_from_postgres))
        return
    if cmd_lower == "/reindex":
        await send_in_chat(chat_id=chat_id, user_id=user_id or 0, text="Запускаю переиндексацию…")
        await send_in_chat(chat_id=chat_id, user_id=user_id or 0, text=await asyncio.to_thread(reindex_from_postgres))
        return
    if cmd_lower.startswith("/addsource"):
        parts = cmd.split(maxsplit=2)
        if len(parts) < 2:
            await send_in_chat(chat_id=chat_id, user_id=user_id or 0, text="Формат: /addsource <путь_к_файлу> [логическое_имя]")
            return
        file_path_raw = parts[1]
        logical_name = parts[2] if len(parts) > 2 else None
        await send_in_chat(chat_id=chat_id, user_id=user_id or 0, text="Добавляю источник и пересобираю индекс…")
        await send_in_chat(
            chat_id=chat_id,
            user_id=user_id or 0,
            text=await asyncio.to_thread(add_source_and_reindex, file_path_raw, logical_name),
        )
        return

    if chat_id is None or chat_id not in chatbot_active_chats:
        return

    key = conversation_key(chat_id, user_id)
    history = get_chat_history(chat_histories, key, maxlen=CHAT_HISTORY_TURNS)
    if history is None:
        return

    await send_in_chat(
        chat_id=chat_id,
        user_id=user_id or 0,
        text="Ваш запрос в обработке, ожидайте",
    )

    snapshot = list(history)
    schedule_background_task(
        _process_chat_request(
            cmd=cmd,
            snapshot=snapshot,
            history=history,
            chat_id=chat_id,
            user_id=user_id or 0,
            send_in_chat=send_in_chat,
        )
    )


async def _process_chat_request(*, cmd: str, snapshot, history, chat_id: int | None, user_id: int, send_in_chat) -> None:
    answer = await answer_from_dataframe_async(cmd, snapshot)
    history.append((cmd, _history_safe_answer(answer)))
    await send_in_chat(chat_id=chat_id, user_id=user_id, text=answer, attachments=[chat_dialog_keyboard()])
