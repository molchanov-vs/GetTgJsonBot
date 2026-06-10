<p align="center">
  <img src="assets/bot-start-page.png" alt="Telegram JSON Echo Bot start page artwork" width="820">
</p>

<h1 align="center">Telegram JSON Echo Bot</h1>

<p align="center">
  <img src="assets/bot-photo-v2.png" alt="Telegram JSON Echo Bot icon" width="140">
</p>

<p align="center">
  A simple Telegram bot that returns message metadata as pretty JSON without saving data.
</p>

The bot does not use a database and does not persist message history. It only reads the incoming Telegram update, extracts useful technical fields, and sends the result back to the user.

## What It Does

Send the bot a message, media, sticker, forwarded message, reply, or reaction. It responds with a compact normalized JSON summary that is easy to read in Telegram and useful for debugging Bot API data.

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

## BotFather Assets

This repository includes ready-to-upload artwork for BotFather:

- Bot profile photo: [`assets/bot-photo-v2.png`](assets/bot-photo-v2.png)
- Alternative profile photo: [`assets/bot-photo.png`](assets/bot-photo.png)
- Bot start page photo: [`assets/bot-start-page.png`](assets/bot-start-page.png)

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
