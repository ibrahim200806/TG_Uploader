# 🤖 Telegram File Sender (Bot + User Fallback)

A simple and secure Python script to send files via a **Telegram bot**, with an optional **user-session fallback** for private delivery.  
Supports automatic **4 GB uploads** for **Telegram Premium** accounts when using a user session string.

---

## ✨ Features

- 📁 Send any file (up to 2 GB with bot, 4 GB with premium user session)
- 🧠 Automatically detects if user account is premium
- 🔁 Falls back to a user account if the bot can’t reach the recipient
- 🧩 `.env` configuration support
- 🔒 Safe to publish: uses `.env.example` (never expose secrets)
- 🧰 CLI-friendly with `argparse`
  ```bash
  python send.py --file ffmpeg.exe --owner 8405296129
