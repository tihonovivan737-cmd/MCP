"""Маршрутизация callback-событий."""

from __future__ import annotations

import logging

from maxapi.exceptions import MaxApiError

from bot_runtime import is_duplicate_callback, log_user_activity

logger = logging.getLogger(__name__)


async def _safe_answer(event) -> None:
    """Подтверждает callback; игнорирует 429 rate-limit от MAX API."""
    try:
        await event.answer()
    except MaxApiError as exc:
        if getattr(exc, "code", None) == 429:
            logger.debug("Callback answer rate-limited (429), skipping: %s", exc)
        else:
            raise
from bot_texts import (
    AGRO_TEXT,
    CALLBACK_CONSULT_TEXT,
    CALLBACK_PLATFORM_TEXT,
    CHAT_BOT_TEXT,
    CONTACTS_MAIN_TEXT,
    EDUCATION_TEXT,
    EVALUATE_MB_TEXT,
    EXPORT_TEXT,
    FIN_GARANT_TEXT,
    HOW_OPEN_BUSINESS_TEXT,
    NF_TEXTS,
    NON_FIN_SERVICES,
    PRODUCTIVITY_TEXT,
    PROP_TEXTS,
)
from bot_ui import (
    back_button,
    chat_dialog_keyboard,
    how_open_business_keyboard,
    send_callback_menu,
    send_contacts,
    send_evaluate_menu,
    send_fin_mb_details,
    send_fin_mb_open,
    send_fin_mb_page,
    send_fin_org,
    send_main_menu,
    send_non_fin_org,
    send_non_fin_page,
    send_property_services,
)


async def handle_callback_event(event, *, upsert_message, chatbot_active_chats: set[int]) -> None:
    callback_id = event.callback.callback_id
    if is_duplicate_callback(callback_id):
        await _safe_answer(event)
        return

    payload = event.callback.payload
    chat_id, user_id = event.get_ids()
    message = event.message
    log_user_activity(action=f"callback:{payload}", user=event.callback.user, chat_id=chat_id)
    await _safe_answer(event)

    if chat_id is not None and payload != "chat_bot_info":
        chatbot_active_chats.discard(chat_id)

    if payload in ("start", "back_to_main", "back_main"):
        await send_main_menu(upsert_message, message, chat_id, user_id)
    elif payload == "how_open_business":
        await upsert_message(message, chat_id, user_id, text=HOW_OPEN_BUSINESS_TEXT, attachments=[how_open_business_keyboard()])
    elif payload in ("non_fin_support", "back_non_fin_org"):
        await send_non_fin_org(upsert_message, message, chat_id, user_id)
    elif payload == "non_fin_mb":
        await send_non_fin_page(upsert_message, message, chat_id, user_id, page_idx=0)
    elif payload.startswith("non_fin_page_"):
        await send_non_fin_page(upsert_message, message, chat_id, user_id, page_idx=int(payload.removeprefix("non_fin_page_")))
    elif payload == "back_non_fin_services":
        await send_non_fin_page(upsert_message, message, chat_id, user_id, page_idx=0)
    elif payload in NF_TEXTS:
        page_idx = next((idx for idx, (code, _) in enumerate(NON_FIN_SERVICES) if code == payload), 0)
        await send_non_fin_page(upsert_message, message, chat_id, user_id, page_idx=page_idx)
    elif payload in ("fin_support", "back_fin_org"):
        await send_fin_org(upsert_message, message, chat_id, user_id)
    elif payload == "fin_mb":
        await send_fin_mb_page(upsert_message, message, chat_id, user_id, page_idx=0)
    elif payload.startswith("fin_mb_page_"):
        await send_fin_mb_page(upsert_message, message, chat_id, user_id, page_idx=int(payload.removeprefix("fin_mb_page_")))
    elif payload.startswith("fin_mb_details_"):
        await send_fin_mb_details(upsert_message, message, chat_id, user_id, page_idx=int(payload.removeprefix("fin_mb_details_")))
    elif payload.startswith("fin_mb_open_"):
        await send_fin_mb_open(upsert_message, message, chat_id, user_id, page_idx=int(payload.removeprefix("fin_mb_open_")))
    elif payload == "fin_garant":
        await upsert_message(message, chat_id, user_id, text=FIN_GARANT_TEXT, attachments=[back_button("back_fin_org")])
    elif payload == "productivity_labor":
        await upsert_message(message, chat_id, user_id, text=PRODUCTIVITY_TEXT, attachments=[back_button("back_main")])
    elif payload == "agro_support":
        await upsert_message(message, chat_id, user_id, text=AGRO_TEXT, attachments=[back_button("back_main")])
    elif payload == "export_coop":
        await upsert_message(message, chat_id, user_id, text=EXPORT_TEXT, attachments=[back_button("back_main")])
    elif payload == "education_services":
        await upsert_message(message, chat_id, user_id, text=EDUCATION_TEXT, attachments=[back_button("back_main")])
    elif payload in ("property_support", "back_property_services"):
        await send_property_services(upsert_message, message, chat_id, user_id)
    elif payload in PROP_TEXTS:
        await upsert_message(message, chat_id, user_id, text=PROP_TEXTS[payload], attachments=[back_button("back_property_services")])
    elif payload in ("contacts_orgs", "back_contacts_orgs"):
        await send_contacts(upsert_message, message, chat_id, user_id)
    elif payload == "contacts_mb":
        await upsert_message(message, chat_id, user_id, text=CONTACTS_MAIN_TEXT, attachments=[back_button("back_contacts_orgs")])
    elif payload in ("callback_request", "back_callback_menu"):
        await send_callback_menu(upsert_message, message, chat_id, user_id)
    elif payload == "callback_consult":
        await upsert_message(message, chat_id, user_id, text=CALLBACK_CONSULT_TEXT, attachments=[back_button("back_callback_menu")])
    elif payload == "callback_platform":
        await upsert_message(message, chat_id, user_id, text=CALLBACK_PLATFORM_TEXT, attachments=[back_button("back_callback_menu")])
    elif payload in ("evaluate_quality", "back_evaluate_menu"):
        await send_evaluate_menu(upsert_message, message, chat_id, user_id)
    elif payload == "evaluate_mb":
        await upsert_message(message, chat_id, user_id, text=EVALUATE_MB_TEXT, attachments=[back_button("back_evaluate_menu")])
    elif payload == "chat_bot_info":
        if chat_id is not None:
            chatbot_active_chats.add(chat_id)
        await upsert_message(message, chat_id, user_id, text=CHAT_BOT_TEXT, attachments=[chat_dialog_keyboard()])
    elif payload == "chat_exit_to_menu":
        if chat_id is not None:
            chatbot_active_chats.discard(chat_id)
        await send_main_menu(upsert_message, message, chat_id, user_id)
