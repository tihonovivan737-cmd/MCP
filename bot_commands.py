"""Обработка текстовых команд и сообщений."""

from __future__ import annotations

import asyncio

from bot_rag import add_source_and_reindex, answer_from_dataframe, list_sources_from_postgres, reindex_from_postgres
from bot_runtime import log_user_activity
from bot_ui import chat_dialog_keyboard, send_main_menu


async def handle_message_event(event, *, send_in_chat, upsert_message, chatbot_active_chats: set[int]) -> None:
    if event.message.sender and event.message.sender.is_bot:
        return
    text = event.message.body.text if event.message.body else None
    if not text:
        return

    chat_id, user_id = event.get_ids()
    log_user_activity(action="message_created", user=event.message.sender, chat_id=chat_id)
    cmd = text.strip().lower()

    if cmd in ("/start", "/menu"):
        if chat_id is not None:
            chatbot_active_chats.discard(chat_id)
        await send_main_menu(upsert_message, None, chat_id, user_id or 0)
        return
    if cmd == "/chat":
        if chat_id is not None:
            chatbot_active_chats.add(chat_id)
        await send_in_chat(chat_id=chat_id, user_id=user_id or 0, text="Режим Чат-бот включен.\n\nЗадайте свой вопрос.", attachments=[chat_dialog_keyboard()])
        return
    if cmd == "/exit":
        if chat_id is not None:
            chatbot_active_chats.discard(chat_id)
        await send_in_chat(chat_id=chat_id, user_id=user_id or 0, text="Режим Чат-бот выключен.")
        return
    if cmd == "/help":
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
    if cmd == "/sources":
        await send_in_chat(chat_id=chat_id, user_id=user_id or 0, text=await asyncio.to_thread(list_sources_from_postgres))
        return
    if cmd == "/reindex":
        await send_in_chat(chat_id=chat_id, user_id=user_id or 0, text="Запускаю переиндексацию…")
        await send_in_chat(chat_id=chat_id, user_id=user_id or 0, text=await asyncio.to_thread(reindex_from_postgres))
        return
    if cmd.startswith("/addsource"):
        parts = text.strip().split(maxsplit=2)
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
    answer = await asyncio.to_thread(answer_from_dataframe, text.strip())
    await send_in_chat(chat_id=chat_id, user_id=user_id or 0, text=answer, attachments=[chat_dialog_keyboard()])
