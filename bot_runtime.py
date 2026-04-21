"""Runtime helpers for logging, deduplication and greeting guard."""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import IO

try:
    import fcntl  # type: ignore
except ImportError:
    fcntl = None  # type: ignore[assignment]
    import msvcrt

_CALLBACK_TTL_SECONDS = 3.0
_BOT_STARTED_TTL_SECONDS = 5.0
_GREETING_COOLDOWN_SECONDS = 120.0

_SEEN_CALLBACKS: dict[str, float] = {}
_SEEN_BOT_STARTED_CHATS: dict[int, float] = {}

_LOGS_DIR = Path(__file__).resolve().parent / "logs"
_USER_ACTIVITY_LOG = _LOGS_DIR / "user_activity.log"
_GREETING_GUARD_FILE = _LOGS_DIR / "greeting_guard.json"

activity_logger = logging.getLogger("bot.activity")


def _lock_file(file_obj: IO[str]) -> None:
    if fcntl is not None:
        fcntl.flock(file_obj.fileno(), fcntl.LOCK_EX)
        return
    file_obj.seek(0, 2)
    if file_obj.tell() == 0:
        file_obj.write(" ")
        file_obj.flush()
    file_obj.seek(0)
    msvcrt.locking(file_obj.fileno(), msvcrt.LK_LOCK, 1)


def _unlock_file(file_obj: IO[str]) -> None:
    if fcntl is not None:
        fcntl.flock(file_obj.fileno(), fcntl.LOCK_UN)
        return
    file_obj.seek(0)
    msvcrt.locking(file_obj.fileno(), msvcrt.LK_UNLCK, 1)


def setup_user_activity_file_logging() -> None:
    if getattr(activity_logger, "_user_file_handler", None):
        return
    _LOGS_DIR.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(_USER_ACTIVITY_LOG, encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(logging.Formatter("%(asctime)s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
    activity_logger.addHandler(file_handler)
    activity_logger.setLevel(logging.INFO)
    activity_logger._user_file_handler = file_handler  # type: ignore[attr-defined]


def is_duplicate_callback(callback_id: str) -> bool:
    now = time.monotonic()
    expired = [cid for cid, ts in _SEEN_CALLBACKS.items() if now - ts > _CALLBACK_TTL_SECONDS]
    for cid in expired:
        _SEEN_CALLBACKS.pop(cid, None)
    if callback_id in _SEEN_CALLBACKS:
        return True
    _SEEN_CALLBACKS[callback_id] = now
    return False


def is_duplicate_bot_started(chat_id: int) -> bool:
    now = time.monotonic()
    expired = [cid for cid, ts in _SEEN_BOT_STARTED_CHATS.items() if now - ts > _BOT_STARTED_TTL_SECONDS]
    for cid in expired:
        _SEEN_BOT_STARTED_CHATS.pop(cid, None)
    if chat_id in _SEEN_BOT_STARTED_CHATS:
        return True
    _SEEN_BOT_STARTED_CHATS[chat_id] = now
    return False


def should_send_greeting(chat_id: int) -> bool:
    _GREETING_GUARD_FILE.parent.mkdir(parents=True, exist_ok=True)
    with _GREETING_GUARD_FILE.open("a+", encoding="utf-8") as file_obj:
        _lock_file(file_obj)
        try:
            file_obj.seek(0)
            raw = file_obj.read().strip()
            data: dict[str, float] = {}
            if raw:
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    data = {}
            now = time.time()
            last_ts = float(data.get(str(chat_id), 0.0))
            if now - last_ts < _GREETING_COOLDOWN_SECONDS:
                return False
            data[str(chat_id)] = now
            file_obj.seek(0)
            file_obj.truncate()
            json.dump(data, file_obj)
            file_obj.flush()
            return True
        finally:
            _unlock_file(file_obj)


def log_user_activity(action: str, user, chat_id: int | None = None) -> None:
    if user is None:
        activity_logger.info(
            "first_name= last_name= user_id= chat_id=%s action=%s user=unknown",
            chat_id,
            action,
        )
        return
    first_name = getattr(user, "first_name", "") or ""
    last_name = getattr(user, "last_name", "") or ""
    user_id = getattr(user, "user_id", None)
    activity_logger.info(
        "first_name=%r last_name=%r user_id=%s chat_id=%s action=%s",
        first_name,
        last_name,
        user_id,
        chat_id,
        action,
    )
