from __future__ import annotations

import asyncio
import json
import logging
import os
from html import escape as html_escape
from datetime import UTC, datetime
from typing import Any

from aiogram import Bot, Dispatcher, Router
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    BufferedInputFile,
    Message,
    MessageEntity,
    MessageReactionCountUpdated,
    MessageReactionUpdated,
    TelegramObject,
    Update,
)


SCHEMA_VERSION = "0.1"
SAFE_MESSAGE_LIMIT = 3800
MEDIA_FIELDS = (
    "animation",
    "audio",
    "document",
    "video",
    "video_note",
    "voice",
    "sticker",
)

router = Router()
logger = logging.getLogger(__name__)


def model_dump(obj: Any) -> Any:
    if obj is None:
        return None
    if isinstance(obj, TelegramObject):
        return obj.model_dump(mode="json", by_alias=True, exclude_none=True)
    if isinstance(obj, list):
        return [model_dump(item) for item in obj]
    if isinstance(obj, dict):
        return {key: model_dump(value) for key, value in obj.items()}
    return obj


def omit_null_values(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: omit_null_values(nested)
            for key, nested in value.items()
            if nested is not None
        }
    if isinstance(value, list):
        return [omit_null_values(item) for item in value if item is not None]
    return value


def enum_value(value: Any) -> Any:
    return getattr(value, "value", value)


def id_as_str(value: Any) -> str | None:
    return None if value is None else str(value)


def datetime_iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.isoformat()
    return None


def datetime_timestamp(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return int(value.timestamp())
    if isinstance(value, int):
        return value
    return None


def utf16_slice(text: str | None, offset: int | None, length: int | None) -> str | None:
    if text is None or offset is None or length is None:
        return None
    raw = text.encode("utf-16-le")
    start = offset * 2
    end = (offset + length) * 2
    return raw[start:end].decode("utf-16-le", errors="ignore")


def normalize_user(user: Any) -> dict[str, Any] | None:
    if user is None:
        return None
    return {
        "id": getattr(user, "id", None),
        "id_str": id_as_str(getattr(user, "id", None)),
        "is_bot": getattr(user, "is_bot", None),
        "first_name": getattr(user, "first_name", None),
        "last_name": getattr(user, "last_name", None),
        "username": getattr(user, "username", None),
        "language_code": getattr(user, "language_code", None),
        "is_premium": getattr(user, "is_premium", None),
    }


def normalize_chat(chat: Any) -> dict[str, Any] | None:
    if chat is None:
        return None
    return {
        "id": getattr(chat, "id", None),
        "id_str": id_as_str(getattr(chat, "id", None)),
        "type": enum_value(getattr(chat, "type", None)),
        "title": getattr(chat, "title", None),
        "username": getattr(chat, "username", None),
        "first_name": getattr(chat, "first_name", None),
        "last_name": getattr(chat, "last_name", None),
        "is_forum": getattr(chat, "is_forum", None),
        "is_direct_messages": getattr(chat, "is_direct_messages", None),
    }


def normalize_message_meta(message: Message) -> dict[str, Any]:
    return {
        "message_id": message.message_id,
        "message_thread_id": getattr(message, "message_thread_id", None),
        "date": datetime_timestamp(getattr(message, "date", None)),
        "date_iso": datetime_iso(getattr(message, "date", None)),
        "edit_date": datetime_timestamp(getattr(message, "edit_date", None)),
        "edit_date_iso": datetime_iso(getattr(message, "edit_date", None)),
        "business_connection_id": getattr(message, "business_connection_id", None),
        "is_topic_message": getattr(message, "is_topic_message", None),
        "is_automatic_forward": getattr(message, "is_automatic_forward", None),
        "has_protected_content": getattr(message, "has_protected_content", None),
    }


def normalize_sender(message: Message) -> dict[str, Any]:
    return {
        "user": normalize_user(getattr(message, "from_user", None)),
        "sender_chat": normalize_chat(getattr(message, "sender_chat", None)),
        "via_bot": normalize_user(getattr(message, "via_bot", None)),
    }


def normalize_text(message: Message) -> dict[str, Any]:
    text = getattr(message, "text", None)
    caption = getattr(message, "caption", None)
    effective_text = text if text is not None else caption
    return {
        "text": text,
        "caption": caption,
        "effective_text": effective_text,
        "length": len(effective_text) if effective_text is not None else 0,
    }


def normalize_entity(
    entity: MessageEntity,
    *,
    source: str,
    source_text: str | None,
) -> dict[str, Any]:
    offset = getattr(entity, "offset", None)
    length = getattr(entity, "length", None)
    return {
        "source": source,
        "type": enum_value(getattr(entity, "type", None)),
        "offset": offset,
        "length": length,
        "text": utf16_slice(source_text, offset, length),
        "url": getattr(entity, "url", None),
        "user": normalize_user(getattr(entity, "user", None)),
        "language": getattr(entity, "language", None),
        "custom_emoji_id": getattr(entity, "custom_emoji_id", None),
    }


def normalize_entities(message: Message) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for entity in getattr(message, "entities", None) or []:
        result.append(normalize_entity(entity, source="text", source_text=message.text))
    for entity in getattr(message, "caption_entities", None) or []:
        result.append(
            normalize_entity(entity, source="caption", source_text=message.caption)
        )
    return result


def file_payload(obj: Any, media_type: str) -> dict[str, Any]:
    payload = {
        "type": media_type,
        "file_id": getattr(obj, "file_id", None),
        "file_unique_id": getattr(obj, "file_unique_id", None),
        "width": getattr(obj, "width", None),
        "height": getattr(obj, "height", None),
        "duration": getattr(obj, "duration", None),
        "file_name": getattr(obj, "file_name", None),
        "mime_type": getattr(obj, "mime_type", None),
        "file_size": getattr(obj, "file_size", None),
        "emoji": getattr(obj, "emoji", None),
        "set_name": getattr(obj, "set_name", None),
        "sticker_type": enum_value(getattr(obj, "type", None)),
        "is_animated": getattr(obj, "is_animated", None),
        "is_video": getattr(obj, "is_video", None),
        "custom_emoji_id": getattr(obj, "custom_emoji_id", None),
    }
    return {key: value for key, value in payload.items() if value is not None}


def normalize_media(message: Message) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []

    photos = getattr(message, "photo", None) or []
    if photos:
        best_index = max(
            range(len(photos)),
            key=lambda i: (
                getattr(photos[i], "file_size", 0) or 0,
                (getattr(photos[i], "width", 0) or 0)
                * (getattr(photos[i], "height", 0) or 0),
            ),
        )
        for index, photo in enumerate(photos):
            payload = file_payload(photo, "photo")
            payload["index"] = index
            payload["best"] = index == best_index
            result.append(payload)

    for field in MEDIA_FIELDS:
        value = getattr(message, field, None)
        if value is not None:
            result.append(file_payload(value, field))

    for field in (
        "paid_media",
        "contact",
        "location",
        "venue",
        "poll",
        "dice",
        "game",
        "web_app_data",
    ):
        value = getattr(message, field, None)
        if value is not None:
            result.append({"type": field, "payload": model_dump(value)})

    return result


def normalize_reply(message: Message) -> dict[str, Any] | None:
    reply = getattr(message, "reply_to_message", None)
    if reply is None:
        return None
    return {
        "message_id": getattr(reply, "message_id", None),
        "chat_id": getattr(getattr(reply, "chat", None), "id", None),
        "from": normalize_user(getattr(reply, "from_user", None)),
        "text_preview": getattr(reply, "text", None) or getattr(reply, "caption", None),
        "quote": model_dump(getattr(message, "quote", None)),
    }


def normalize_forward(message: Message) -> dict[str, Any] | None:
    origin = getattr(message, "forward_origin", None)
    is_automatic = getattr(message, "is_automatic_forward", None)
    if origin is None and is_automatic is None:
        return None
    return {
        "origin": model_dump(origin),
        "is_automatic_forward": is_automatic,
    }


def add_unique_custom_emoji(
    result: list[dict[str, Any]], seen: set[tuple[Any, ...]], item: dict[str, Any]
) -> None:
    custom_emoji_id = item.get("custom_emoji_id")
    if not custom_emoji_id:
        return
    if str(item.get("source", "")).startswith("raw_update") and any(
        str(existing.get("custom_emoji_id")) == str(custom_emoji_id)
        for existing in result
    ):
        return
    key = (
        item.get("source"),
        str(custom_emoji_id),
        item.get("offset"),
        item.get("length"),
        item.get("text"),
        item.get("emoji"),
        item.get("file_id"),
    )
    if key in seen:
        return
    seen.add(key)
    result.append(item)


def collect_custom_emoji_from_raw(
    value: Any,
    *,
    result: list[dict[str, Any]],
    seen: set[tuple[Any, ...]],
    path: str,
) -> None:
    if isinstance(value, dict):
        custom_emoji_id = value.get("custom_emoji_id") or value.get("icon_custom_emoji_id")
        if custom_emoji_id:
            add_unique_custom_emoji(
                result,
                seen,
                {"source": path, "custom_emoji_id": custom_emoji_id},
            )
        for key, nested in value.items():
            collect_custom_emoji_from_raw(
                nested, result=result, seen=seen, path=f"{path}.{key}"
            )
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            collect_custom_emoji_from_raw(
                nested, result=result, seen=seen, path=f"{path}[{index}]"
            )


def normalize_custom_emoji(
    *,
    entities: list[dict[str, Any]],
    media: list[dict[str, Any]],
    raw_update: dict[str, Any],
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()

    for entity in entities:
        add_unique_custom_emoji(
            result,
            seen,
            {
                "source": f"message.{entity['source']}_entities",
                "custom_emoji_id": entity.get("custom_emoji_id"),
                "text": entity.get("text"),
                "offset": entity.get("offset"),
                "length": entity.get("length"),
            },
        )

    for item in media:
        add_unique_custom_emoji(
            result,
            seen,
            {
                "source": f"message.{item.get('type')}",
                "custom_emoji_id": item.get("custom_emoji_id"),
                "emoji": item.get("emoji"),
                "file_id": item.get("file_id"),
            },
        )

    collect_custom_emoji_from_raw(
        raw_update, result=result, seen=seen, path="raw_update"
    )
    return result


def normalize_message_update(
    *,
    kind: str,
    message: Message,
    event_update: Update | None,
) -> dict[str, Any]:
    raw_update = (
        model_dump(event_update)
        if event_update is not None
        else {kind: model_dump(message)}
    )
    entities = normalize_entities(message)
    media = normalize_media(message)
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": kind,
        "update_id": getattr(event_update, "update_id", None),
        "received_at": datetime.now(UTC).isoformat(),
        "message": normalize_message_meta(message),
        "sender": normalize_sender(message),
        "chat": normalize_chat(getattr(message, "chat", None)),
        "text": normalize_text(message),
        "entities": entities,
        "custom_emoji": normalize_custom_emoji(
            entities=entities, media=media, raw_update=raw_update
        ),
        "media": media,
        "reply": normalize_reply(message),
        "forward": normalize_forward(message),
        "reaction": None,
    }


def normalize_reaction_update(
    *,
    kind: str,
    reaction: MessageReactionUpdated | MessageReactionCountUpdated,
    event_update: Update | None,
) -> dict[str, Any]:
    raw_update = (
        model_dump(event_update)
        if event_update is not None
        else {kind: model_dump(reaction)}
    )
    reaction_payload = {
        "chat": normalize_chat(getattr(reaction, "chat", None)),
        "message_id": getattr(reaction, "message_id", None),
        "date": datetime_timestamp(getattr(reaction, "date", None)),
        "date_iso": datetime_iso(getattr(reaction, "date", None)),
    }

    if isinstance(reaction, MessageReactionUpdated):
        reaction_payload.update(
            {
                "user": normalize_user(getattr(reaction, "user", None)),
                "actor_chat": normalize_chat(getattr(reaction, "actor_chat", None)),
                "old_reaction": model_dump(getattr(reaction, "old_reaction", None)),
                "new_reaction": model_dump(getattr(reaction, "new_reaction", None)),
            }
        )
    else:
        reaction_payload["reactions"] = model_dump(getattr(reaction, "reactions", None))

    return {
        "schema_version": SCHEMA_VERSION,
        "kind": kind,
        "update_id": getattr(event_update, "update_id", None),
        "received_at": datetime.now(UTC).isoformat(),
        "message": {
            "message_id": getattr(reaction, "message_id", None),
            "date": datetime_timestamp(getattr(reaction, "date", None)),
            "date_iso": datetime_iso(getattr(reaction, "date", None)),
        },
        "sender": {
            "user": normalize_user(getattr(reaction, "user", None)),
            "sender_chat": normalize_chat(getattr(reaction, "actor_chat", None)),
            "via_bot": None,
        },
        "chat": normalize_chat(getattr(reaction, "chat", None)),
        "text": {},
        "entities": [],
        "custom_emoji": normalize_custom_emoji(
            entities=[], media=[], raw_update=raw_update
        ),
        "media": [],
        "reply": None,
        "forward": None,
        "reaction": reaction_payload,
    }


async def send_json_answer(
    *,
    bot: Bot,
    chat_id: int,
    payload: dict[str, Any],
    reply_to_message_id: int | None = None,
) -> None:
    payload = omit_null_values(payload)
    json_text = json.dumps(payload, ensure_ascii=False, indent=2)
    if len(json_text) <= SAFE_MESSAGE_LIMIT:
        text = (
            '<pre><code class="language-json">'
            f"{html_escape(json_text)}"
            "</code></pre>"
        )
        try:
            await bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode=ParseMode.HTML,
                reply_to_message_id=reply_to_message_id,
                disable_web_page_preview=True,
            )
            return
        except TelegramBadRequest:
            logger.exception("Formatted JSON message was rejected; sending document")

    await send_json_document(
        bot=bot,
        chat_id=chat_id,
        payload=payload,
        json_text=json_text,
        reply_to_message_id=reply_to_message_id,
    )


async def send_json_document(
    *,
    bot: Bot,
    chat_id: int,
    payload: dict[str, Any],
    json_text: str,
    reply_to_message_id: int | None = None,
) -> None:
    update_id = payload.get("update_id") or "unknown"
    document = BufferedInputFile(
        json_text.encode("utf-8"),
        filename=f"telegram_update_{update_id}.json",
    )
    await bot.send_document(
        chat_id=chat_id,
        document=document,
        caption="<b>JSON слишком большой</b>\nОтправляю полную версию файлом.",
        parse_mode=ParseMode.HTML,
        reply_to_message_id=reply_to_message_id,
    )


@router.message(CommandStart())
async def start(message: Message) -> None:
    await message.answer(
        "Пришлите мне сообщение, пересланное сообщение, медиа, стикер, custom emoji "
        "или реакцию. Я верну JSON с техническими полями Telegram."
    )


@router.message(Command("help"))
async def help_command(message: Message) -> None:
    await message.answer(
        "Поддерживаются обычные и отредактированные сообщения, посты каналов, "
        "медиа, entities, custom emoji, ответы, пересылки и реакции. Ничего не "
        "сохраняется: бот только формирует JSON и отправляет его обратно."
    )


@router.message()
async def handle_message(
    message: Message, bot: Bot, event_update: Update | None = None
) -> None:
    payload = normalize_message_update(
        kind="message", message=message, event_update=event_update
    )
    await send_json_answer(
        bot=bot,
        chat_id=message.chat.id,
        payload=payload,
        reply_to_message_id=message.message_id,
    )


@router.edited_message()
async def handle_edited_message(
    edited_message: Message, bot: Bot, event_update: Update | None = None
) -> None:
    payload = normalize_message_update(
        kind="edited_message", message=edited_message, event_update=event_update
    )
    await send_json_answer(
        bot=bot,
        chat_id=edited_message.chat.id,
        payload=payload,
        reply_to_message_id=edited_message.message_id,
    )


@router.channel_post()
async def handle_channel_post(
    channel_post: Message, bot: Bot, event_update: Update | None = None
) -> None:
    payload = normalize_message_update(
        kind="channel_post", message=channel_post, event_update=event_update
    )
    await send_json_answer(
        bot=bot,
        chat_id=channel_post.chat.id,
        payload=payload,
        reply_to_message_id=channel_post.message_id,
    )


@router.edited_channel_post()
async def handle_edited_channel_post(
    edited_channel_post: Message, bot: Bot, event_update: Update | None = None
) -> None:
    payload = normalize_message_update(
        kind="edited_channel_post",
        message=edited_channel_post,
        event_update=event_update,
    )
    await send_json_answer(
        bot=bot,
        chat_id=edited_channel_post.chat.id,
        payload=payload,
        reply_to_message_id=edited_channel_post.message_id,
    )


@router.message_reaction()
async def handle_message_reaction(
    message_reaction: MessageReactionUpdated,
    bot: Bot,
    event_update: Update | None = None,
) -> None:
    payload = normalize_reaction_update(
        kind="message_reaction",
        reaction=message_reaction,
        event_update=event_update,
    )
    await send_json_answer(
        bot=bot,
        chat_id=message_reaction.chat.id,
        payload=payload,
        reply_to_message_id=message_reaction.message_id,
    )


@router.message_reaction_count()
async def handle_message_reaction_count(
    message_reaction_count: MessageReactionCountUpdated,
    bot: Bot,
    event_update: Update | None = None,
) -> None:
    payload = normalize_reaction_update(
        kind="message_reaction_count",
        reaction=message_reaction_count,
        event_update=event_update,
    )
    await send_json_answer(
        bot=bot,
        chat_id=message_reaction_count.chat.id,
        payload=payload,
        reply_to_message_id=message_reaction_count.message_id,
    )


async def main() -> None:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError("BOT_TOKEN is required")

    bot = Bot(token=token)
    dispatcher = Dispatcher()
    dispatcher.include_router(router)

    allowed_updates = dispatcher.resolve_used_update_types()
    logger.info("Starting bot with allowed update types: %s", allowed_updates)
    await dispatcher.start_polling(bot, allowed_updates=allowed_updates)


if __name__ == "__main__":
    asyncio.run(main())
