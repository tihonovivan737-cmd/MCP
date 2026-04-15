"""Экраны и кнопки бота (UI-слой)."""

from __future__ import annotations

import re
from typing import Awaitable, Callable

from maxapi.enums.parse_mode import TextFormat
from maxapi.types import CallbackButton, LinkButton
from maxapi.utils.inline_keyboard import InlineKeyboardBuilder
from maxapi.utils.formatting import Link

from bot_texts import (
    CALLBACK_MENU_TEXT,
    EVALUATE_MENU_TEXT,
    FIN_MB_TEXT,
    MAIN_MENU_TEXT,
    NF_TEXTS,
    NON_FIN_SERVICES,
)

UpsertFn = Callable[..., Awaitable[None]]
_PHONE_RE = re.compile(r"((?:\+7|8)[\d\s\-\(\)]{9,})")


def back_to_main_button():
    builder = InlineKeyboardBuilder()
    builder.row(CallbackButton(text="◀️ В главное меню", payload="back_to_main"))
    return builder.as_markup()


def back_button(payload: str, text: str = "⬅️ Вернуться назад"):
    builder = InlineKeyboardBuilder()
    builder.row(CallbackButton(text=text, payload=payload))
    return builder.as_markup()


def how_open_business_keyboard() -> object:
    builder = InlineKeyboardBuilder()
    builder.row(
        LinkButton(
            text="Подробнее о открытии расчётного счёта",
            url="https://xn---24-9cdulgg0aog6b.xn--p1ai/navigator/sodeystvie-v-registratsii-biznesa-i-otkrytii-raschetnogo-scheta-v-bankakh-partnerakh/",
        )
    )
    builder.row(
        LinkButton(
            text='Центр "Мой бизнес"',
            url="https://мойбизнес-24.рф/o-proekte/predstavitelstva-v-krasnoyarskom-krae/",
        )
    )
    builder.row(LinkButton(text="МСП.РФ", url="https://мсп.рф/"))
    builder.row(LinkButton(text="Инструкция по регистрации (ООО, ИП)", url="https://disk.yandex.ru/i/EctN8PXdwMY_YQ"))
    builder.row(CallbackButton(text="◀️ В главное меню", payload="back_main"))
    return builder.as_markup()


def chat_dialog_keyboard() -> object:
    builder = InlineKeyboardBuilder()
    builder.row(CallbackButton(text="🚪 Выйти из диалога", payload="chat_exit_to_menu"))
    return builder.as_markup()


def split_text_pages(text: str, max_len: int = 900) -> list[str]:
    parts = [p.strip() for p in text.split("\n\n") if p.strip()]
    pages: list[str] = []
    cur = ""
    for part in parts:
        candidate = f"{cur}\n\n{part}".strip() if cur else part
        if len(candidate) <= max_len:
            cur = candidate
            continue
        if cur:
            pages.append(cur)
        cur = part
    if cur:
        pages.append(cur)
    return pages or [text]


FIN_MB_PAGES = split_text_pages(FIN_MB_TEXT)


def fin_mb_keyboard(page_idx: int) -> object:
    total = len(FIN_MB_PAGES)
    prev_idx = max(page_idx - 1, 0)
    next_idx = min(page_idx + 1, total - 1)
    builder = InlineKeyboardBuilder()
    builder.row(
        CallbackButton(text="⬅️", payload=f"fin_mb_page_{prev_idx}"),
        CallbackButton(text=str(page_idx + 1), payload=f"fin_mb_page_{page_idx}"),
        CallbackButton(text="➡️", payload=f"fin_mb_page_{next_idx}"),
        CallbackButton(text=str(total), payload=f"fin_mb_page_{total - 1}"),
    )
    builder.row(
        LinkButton(
            text="↗️ Открыть",
            url="https://xn---24-9cdulgg0aog6b.xn--p1ai/sections/mikrofinansirovanie/#page-nav-1",
        ),
    )
    builder.row(CallbackButton(text="⬅️ Вернуться назад", payload="back_fin_org"))
    return builder.as_markup()


def split_text_and_links(text: str) -> tuple[str, list[tuple[str, str]]]:
    lines = text.splitlines()
    content_lines: list[str] = []
    links: list[tuple[str, str]] = []
    for line in lines:
        raw = line.strip()
        if raw.lower() in {"подать заявку:", "подать заявку"}:
            continue
        if "http://" in raw or "https://" in raw:
            prefix = raw
            url = ""
            if ":" in raw:
                left, right = raw.split(":", 1)
                prefix = left.strip("• ").strip()
                url = right.strip()
            else:
                for part in raw.split():
                    if part.startswith("http://") or part.startswith("https://"):
                        url = part
                        break
                prefix = "Перейти по ссылке"
            if url.startswith("http://") or url.startswith("https://"):
                label = prefix or "Перейти по ссылке"
                if "сайт" in label.lower():
                    label = "Подать заявку"
                if label.lower().startswith("инструкция"):
                    label = "Инструкция по подаче заявки"
                links.append((label, url))
                continue
        content_lines.append(line)
    msp_links = [item for item in links if "мсп.рф" in item[0].lower() or "мсп.рф" in item[1].lower()]
    other_links = [item for item in links if item not in msp_links]
    return "\n".join(content_lines).strip(), other_links + msp_links


def format_phone_links(text: str) -> tuple[str, TextFormat | None]:
    has_phone = False
    formatted_lines: list[str] = []
    for line in text.splitlines():
        match = _PHONE_RE.search(line)
        if not match:
            formatted_lines.append(line)
            continue

        phone = match.group(1).strip()
        tel = re.sub(r"[^\d+]", "", phone)
        if tel.startswith("8"):
            tel = "+7" + tel[1:]
        elif tel.startswith("7"):
            tel = "+" + tel
        if not tel.startswith("+7"):
            formatted_lines.append(line)
            continue

        has_phone = True
        formatted_lines.append(line.replace(phone, Link(phone, url=f"tel:{tel}").as_markdown(), 1))

    return "\n".join(formatted_lines), TextFormat.MARKDOWN if has_phone else None


async def send_info_text(
    upsert: UpsertFn,
    message,
    chat_id: int | None,
    user_id: int,
    *,
    text: str,
    back_payload: str,
    back_text: str = "⬅️ Вернуться назад",
):
    body, links = split_text_and_links(text)
    formatted_body, text_format = format_phone_links(body or text)
    builder = InlineKeyboardBuilder()
    for label, url in links:
        builder.row(LinkButton(text=label, url=url))
    builder.row(CallbackButton(text=back_text, payload=back_payload))
    await upsert(message, chat_id, user_id, text=formatted_body, attachments=[builder.as_markup()], format=text_format)


async def send_main_menu(upsert: UpsertFn, message, chat_id: int | None, user_id: int):
    builder = InlineKeyboardBuilder()
    builder.row(CallbackButton(text="📋 Открыть бизнес", payload="how_open_business"))
    builder.row(CallbackButton(text="🤝 Нефинансовая поддержка", payload="non_fin_support"))
    builder.row(CallbackButton(text="💰 Фин. поддержка", payload="fin_support"))
    builder.row(CallbackButton(text="📈 Производительность", payload="productivity_labor"))
    builder.row(CallbackButton(text="🌾 Поддержка АПК", payload="agro_support"))
    builder.row(CallbackButton(text="🌍 Экспорт", payload="export_coop"))
    builder.row(CallbackButton(text="🎓 Обучение", payload="education_services"))
    builder.row(CallbackButton(text="🏢 Имущественная", payload="property_support"))
    builder.row(CallbackButton(text="📞 Контакты", payload="contacts_orgs"))
    builder.row(CallbackButton(text="☎️ Обратный звонок", payload="callback_request"))
    builder.row(CallbackButton(text="⭐ Оценить услуги", payload="evaluate_quality"))
    builder.row(CallbackButton(text="🤖 Чат-бот", payload="chat_bot_info"))
    await upsert(message, chat_id, user_id, text=MAIN_MENU_TEXT, attachments=[builder.as_markup()])


async def send_non_fin_page(upsert: UpsertFn, message, chat_id: int | None, user_id: int, page_idx: int):
    total = len(NON_FIN_SERVICES)
    page_idx = max(0, min(page_idx, total - 1))
    payload, title = NON_FIN_SERVICES[page_idx]
    body = NF_TEXTS.get(payload, "Информация по услуге временно недоступна.")
    text_body, links = split_text_and_links(body)
    page_text = f"{page_idx + 1}. {title}\n\n{text_body}"
    prev_idx = max(page_idx - 1, 0)
    next_idx = min(page_idx + 1, total - 1)
    builder = InlineKeyboardBuilder()
    for label, url in links:
        builder.row(LinkButton(text=label, url=url))
    builder.row(
        CallbackButton(text="⬅️", payload=f"non_fin_page_{prev_idx}"),
        CallbackButton(text=str(page_idx + 1), payload=f"non_fin_page_{page_idx}"),
        CallbackButton(text="➡️", payload=f"non_fin_page_{next_idx}"),
        CallbackButton(text=str(total), payload=f"non_fin_page_{total - 1}"),
    )
    builder.row(CallbackButton(text="⬅️ Вернуться назад", payload="back_non_fin_org"))
    await upsert(message, chat_id, user_id, text=page_text, attachments=[builder.as_markup()])


async def send_non_fin_org(upsert: UpsertFn, message, chat_id: int | None, user_id: int):
    builder = InlineKeyboardBuilder()
    builder.row(CallbackButton(text='Центр "Мой бизнес"', payload="non_fin_mb"))
    builder.row(CallbackButton(text="◀️ В главное меню", payload="back_main"))
    await upsert(message, chat_id, user_id, text="Выберите организацию:", attachments=[builder.as_markup()])


async def send_fin_org(upsert: UpsertFn, message, chat_id: int | None, user_id: int):
    builder = InlineKeyboardBuilder()
    builder.row(CallbackButton(text='Мой бизнес (займы)', payload="fin_mb"))
    builder.row(CallbackButton(text="Гарантийный фонд", payload="fin_garant"))
    builder.row(CallbackButton(text="⬅️ Вернуться назад", payload="back_main"))
    builder.row(CallbackButton(text="◀️ В главное меню", payload="back_main"))
    await upsert(message, chat_id, user_id, text="Выберите организацию:", attachments=[builder.as_markup()])


async def send_property_services(upsert: UpsertFn, message, chat_id: int | None, user_id: int):
    builder = InlineKeyboardBuilder()
    builder.row(CallbackButton(text="Аренда коворкинга", payload="prop_kovorking"))
    builder.row(CallbackButton(text="Аренда переговорной", payload="prop_peregovornaya"))
    builder.row(CallbackButton(text="Аренда конференц-зала", payload="prop_conf_zal"))
    builder.row(CallbackButton(text="Аренда малого зала", payload="prop_maly_zal"))
    builder.row(CallbackButton(text="⬅️ Вернуться назад", payload="back_main"))
    builder.row(CallbackButton(text="◀️ В главное меню", payload="back_main"))
    await upsert(message, chat_id, user_id, text="Выберите услугу:", attachments=[builder.as_markup()])


async def send_contacts(upsert: UpsertFn, message, chat_id: int | None, user_id: int):
    builder = InlineKeyboardBuilder()
    builder.row(CallbackButton(text='Центр "Мой бизнес"', payload="contacts_mb"))
    builder.row(CallbackButton(text="⬅️ Вернуться назад", payload="back_main"))
    builder.row(CallbackButton(text="◀️ В главное меню", payload="back_main"))
    await upsert(message, chat_id, user_id, text="Выберите организацию:", attachments=[builder.as_markup()])


async def send_callback_menu(upsert: UpsertFn, message, chat_id: int | None, user_id: int):
    builder = InlineKeyboardBuilder()
    builder.row(CallbackButton(text='Консультация Мой бизнес', payload="callback_consult"))
    builder.row(CallbackButton(text="Проблемы с МСП.РФ", payload="callback_platform"))
    builder.row(CallbackButton(text="⬅️ Вернуться назад", payload="back_main"))
    builder.row(CallbackButton(text="◀️ В главное меню", payload="back_main"))
    await upsert(message, chat_id, user_id, text=CALLBACK_MENU_TEXT, attachments=[builder.as_markup()])


async def send_evaluate_menu(upsert: UpsertFn, message, chat_id: int | None, user_id: int):
    builder = InlineKeyboardBuilder()
    builder.row(CallbackButton(text='Центр "Мой бизнес"', payload="evaluate_mb"))
    builder.row(CallbackButton(text="⬅️ Вернуться назад", payload="back_main"))
    builder.row(CallbackButton(text="◀️ В главное меню", payload="back_main"))
    await upsert(message, chat_id, user_id, text=EVALUATE_MENU_TEXT, attachments=[builder.as_markup()])


async def send_fin_mb_page(upsert: UpsertFn, message, chat_id: int | None, user_id: int, page_idx: int):
    total = len(FIN_MB_PAGES)
    page_idx = max(0, min(page_idx, total - 1))
    await upsert(message, chat_id, user_id, text=FIN_MB_PAGES[page_idx], attachments=[fin_mb_keyboard(page_idx)])


async def send_fin_mb_details(upsert: UpsertFn, message, chat_id: int | None, user_id: int, page_idx: int):
    builder = InlineKeyboardBuilder()
    builder.row(CallbackButton(text="⬅️ Вернуться назад", payload=f"fin_mb_page_{page_idx}"))
    await upsert(message, chat_id, user_id, text=FIN_MB_TEXT, attachments=[builder.as_markup()])


async def send_fin_mb_open(upsert: UpsertFn, message, chat_id: int | None, user_id: int, page_idx: int):
    builder = InlineKeyboardBuilder()
    builder.row(
        LinkButton(
            text="↗️ Открыть",
            url="https://xn---24-9cdulgg0aog6b.xn--p1ai/sections/mikrofinansirovanie/#page-nav-1",
        ),
    )
    builder.row(CallbackButton(text="⬅️ Вернуться назад", payload=f"fin_mb_page_{page_idx}"))
    await upsert(
        message,
        chat_id,
        user_id,
        text="Подробнее о финансовой поддержке:\nhttps://xn---24-9cdulgg0aog6b.xn--p1ai/sections/mikrofinansirovanie/#page-nav-1",
        attachments=[builder.as_markup()],
    )
