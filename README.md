# 🤖 Telegram File Sender (Bot + User Fallback)

[![Python](https://img.shields.io/badge/python-3.9%2B-blue)](https://www.python.org/)
[![Pyrogram](https://img.shields.io/badge/pyrogram-2.x-orange)](https://docs.pyrogram.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

A secure, lightweight Python utility to send files over Telegram using a **bot**, with an optional **user-session fallback** for delivery when the bot cannot reach the recipient. If you provide a **user session string** that belongs to a **Telegram Premium** account, the tool enables **4 GB upload support** for that session.

---

## Table of contents

- [Features](#features)  
- [Quick start](#quick-start)  
- [Configuration (`.env` / `config.env`)](#configuration-configenv)  
- [Usage examples](#usage-examples)  
- [Advanced & CLI options](#advanced--cli-options)  
- [Docker](#docker)  
- [Troubleshooting & FAQ](#troubleshooting--faq)  
- [Security, privacy & legal](#security-privacy--legal)  
- [Development & contribution](#development--contribution)  
- [Changelog](#changelog)  
- [License](#license)

---

## Features

- ✅ Send files using a Telegram **bot** (`BOT_TOKEN`)  
- 🔁 Automatic fallback to a **user session** (session string or phone) if bot can't reach the recipient  
- 🧠 Detects **Telegram Premium** user accounts and enables **4 GB** single-file support via user session  
- 📦 CLI-friendly with `argparse` and single-file script (`send.py` / `main.py`)  
- 📄 `.env.example` and `.gitignore` ready for safe GitHub usage  
- 📊 Progress printing with average/instant speed

---

## Quick start

1. Clone the repository:
   ```bash
   git clone [https://github.com/ibrahim200806/TG_Uploader](https://github.com/ibrahim200806/TG_Uploader).git
   cd TG_Uploader
Copy example env and edit:

bash
Copy code
cp .env.example .env
# edit .env with your keys
Create a virtualenv and install dependencies:

bash
Copy code
python3 -m venv venv
source venv/bin/activate     # or: venv\Scripts\activate on Windows
pip install -r requirements.txt
Send a file (example):

bash
Copy code
python send.py --file file.zip --owner 8405296129
Configuration (config.env / .env)
Use .env (or config.env depending on script) to store credentials. Never commit your real .env.

Example .env entries:

env
Copy code
API_ID=12345678
API_HASH=abcd1234efgh5678ijkl9012mnop3456
BOT_TOKEN=1234567890:ABCDEF1234567890abcdef1234567890

# optional fallback (recommended: session string)
USER_SESSION_STRING=
PHONE_NUMBER=
API_ID and API_HASH: from https://my.telegram.org/apps

BOT_TOKEN: from @BotFather

USER_SESSION_STRING: Pyrogram session string (recommended for fallback and premium detection)

PHONE_NUMBER: fallback interactive login (less recommended for headless automation)

Use .env.example as a template.

Usage examples
Basic (bot only):

bash
Copy code
python send.py --file /path/to/file.mp4 --owner 8405296129
User-session fallback (session string):

bash
Copy code
python send.py --file /path/to/file.mp4 --owner @myfriend --user-session-string "1A2b3C..."
Fallback via phone (interactive; not recommended in headless servers):

bash
Copy code
python send.py --file /path/to/file.mp4 --owner @myfriend --phone +15551234567
Override config values on CLI:

bash
Copy code
python send.py --file big.zip --owner 123456789 --api-id 12345678 --api-hash abcdef --bot-token "..."
Advanced & CLI options
Command line options (short summary):

--file, -f — Path to file to send (required)

--owner, -o — Telegram user ID (numeric) or @username (required)

--api-id — Override API_ID from env

--api-hash — Override API_HASH from env

--bot-token — Override BOT_TOKEN from env

--phone — Phone number for user fallback (interactive)

--user-session-string — User session string (preferred fallback)

Behavior notes
If you pass USER_SESSION_STRING and that user is Premium, the script sets MAX_SPLIT_SIZE to 4,194,304,000 bytes (approx 4.194 GB) — consistent with the code defaults. If you'd prefer 4 × 1024³ bytes exactly, adjust constants in code.

Bot uploads are limited by Telegram to 2 GB; user-session (premium) can be larger.

Docker
A minimal Dockerfile example to run send.py in an isolated container. Use with caution (secrets must be injected via environment or Docker secrets).

dockerfile
Copy code
FROM python:3.10-slim

WORKDIR /app
COPY . /app
RUN pip install --no-cache-dir -r requirements.txt

# copy a default config example; override with real env on run
COPY .env.example /app/.env

ENTRYPOINT ["python", "send.py"]
Run container (example):

bash
Copy code
docker build -t tg-sender .
docker run --rm -e API_ID=... -e API_HASH=... -e BOT_TOKEN=... -v /path/to/files:/data tg-sender --file /data/ffmpeg.exe --owner 8405296129
Troubleshooting & FAQ
Q: I see RuntimeWarning: coroutine 'X' was never awaited
A: Use the async-enabled script provided (asyncio.run(main(args))) or ensure you're running Pyrogram v2+ and awaiting coroutines. See requirements.txt.

Q: Bot says PeerIdInvalid or test message fails
A: The target user likely hasn't started the bot (they must open a chat and run /start) or has privacy settings blocking the bot. Use user-session fallback or ask the recipient to start the bot.

Q: Upload fails for big files
A: Bots are bound by Telegram limits (2 GB). Use a premium user session to support 4 GB uploads. Also ensure sufficient disk and memory, and stable network.

Q: How do I get a USER_SESSION_STRING?
A: You can generate it using Pyrogram’s interactive scripts or your own code that logs in the user and exports session_string. Only generate for your own account.

Q: Script prints no message_id or returns None for message ids
A: Depending on Pyrogram version and response parsing, message objects may differ. Ensure you’re using a matching Pyrogram version and tgcrypto for speed.

Security, privacy & legal
By using this project you agree to:

Only operate with accounts and bots you own. Never use credentials you do not own.

Not use this tool to send malware, illegal content, copyrighted files without permission, or spam.

Accept that automating other users' accounts or sending unsolicited bulk messages may violate Telegram Terms of Service and local laws.

Security checklist

Never commit .env with real values. Use .env.example in repo.

Rotate tokens immediately if they are ever exposed.

Use Docker secrets or a secrets manager for production.

Limit and monitor access to session files.

Telegram ToS: https://core.telegram.org/api/terms

Development & contribution
Contributions welcome! Suggested workflow:

Fork the repository.

Create a feature branch: git checkout -b feat/your-feature.

Make changes, run tests, format code.

Submit a Pull Request with a clear description.

Coding style

Use black for formatting.

Keep changes minimal and well-documented.

Changelog
v1.0.0 — Initial release: bot send, user fallback, premium detection, CLI.

(Add your project-specific changelog here as you make releases.)

License
This project is licensed under the MIT License — see LICENSE for details.

sql
Copy code
MIT License

Copyright (c) 2025
