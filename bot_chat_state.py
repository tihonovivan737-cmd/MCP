from __future__ import annotations

from collections import deque
from typing import TypeAlias

ChatTurn: TypeAlias = tuple[str, str]
ChatHistory: TypeAlias = deque[ChatTurn]
ChatHistoryStore: TypeAlias = dict[int, ChatHistory]


def conversation_key(chat_id: int | None, user_id: int | None) -> int | None:
    if chat_id is not None:
        return chat_id
    if user_id is None:
        return None
    return -user_id


def get_chat_history(store: ChatHistoryStore, key: int | None, *, maxlen: int) -> ChatHistory | None:
    if key is None:
        return None
    history = store.get(key)
    if history is None:
        history = deque(maxlen=maxlen)
        store[key] = history
    return history


def reset_chat_state(
    active_chats: set[int],
    histories: ChatHistoryStore,
    *,
    chat_id: int | None,
    user_id: int | None,
) -> None:
    if chat_id is not None:
        active_chats.discard(chat_id)
    key = conversation_key(chat_id, user_id)
    if key is not None:
        histories.pop(key, None)
