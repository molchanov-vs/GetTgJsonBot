# Telegram JSON Echo Bot

A minimal Telegram bot that returns a compact, pretty-printed JSON summary of messages sent to it.

The bot does not use a database and does not persist message history. It only reads the incoming Telegram update, extracts useful technical fields, and sends the result back to the user.

## Features

- Message, chat, and user IDs.
- Sender, chat, and user metadata.
- Text, captions, entities, and caption entities.
- Custom emoji IDs from text entities, stickers, reactions, and other supported update fields.
- Media `file_id` and `file_unique_id` for photos, videos, documents, voice messages, audio, animations, and stickers.
- Reply and forward metadata.
- Compact normalized output without the full raw Telegram update.
- Pretty JSON output in a Telegram code block with `json` syntax highlighting.
- Automatic `.json` file response when the payload is too large for a Telegram message.

## Requirements

- Docker and Docker Compose.
- A Telegram bot token from [@BotFather](https://t.me/BotFather).

## Configuration

Create a `.env` file in the project root:

```env
BOT_TOKEN=123456789:your_token
```

You can use [.env.example](.env.example) as a template.

## Run

```bash
docker compose up --build
```

To run it in the background:

```bash
docker compose up -d --build
```

View logs:

```bash
docker compose logs -f bot
```

Stop the bot:

```bash
docker compose down
```

## Privacy

The bot does not store messages, updates, files, or user history. The response can still contain personal data that Telegram sent to the bot, such as user IDs, usernames, names, language codes, message text, and file metadata.
