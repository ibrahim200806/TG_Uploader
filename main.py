#!/usr/bin/env python3
"""
main.py

Send a file to a Telegram user using a bot, with optional user-session fallback.
Fixed to properly await all Pyrogram coroutines (no 'coroutine was never awaited' warnings).
"""

import os
import sys
import time
import asyncio
import argparse
from pathlib import Path

from pyrogram import Client, enums
from pyrogram.errors import (
    Forbidden, PeerIdInvalid, RPCError, FloodWait, UserIsBot
)
from dotenv import load_dotenv
load_dotenv('config.env', override=True)
# ---------- Config defaults (from env) ----------
API_ID = int(os.getenv("API_ID", "0") or 0)
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
USER_SESSION_STRING = os.getenv("USER_SESSION_STRING", "")
PHONE_NUMBER = os.getenv("PHONE_NUMBER", "")  # fallback phone if supplied by env

# ---------- Progress helper ----------
class ProgressPrinter:
    def __init__(self, total):
        self.total = float(total) if total else 0.0
        self.start = time.time()
        self.last = 0
        self.last_time = self.start

    def callback(self, current, total):
        now = time.time()
        if now - self.last_time < 0.6 and current < total:
            self.last = current
            return
        elapsed = now - self.start
        avg = (current / 1024 / 1024) / (elapsed if elapsed > 0 else 1e-6)
        delta = current - self.last
        inst_elapsed = now - self.last_time if (now - self.last_time) > 0 else 1e-6
        inst = (delta / 1024 / 1024) / inst_elapsed
        pct = (current / total) * 100 if total else 0.0
        print(f"\r{current/1024/1024:8.2f}/{total/1024/1024:8.2f} MB — {pct:6.2f}% — avg {avg:6.2f} MB/s — inst {inst:6.2f} MB/s", end="", flush=True)
        self.last = current
        self.last_time = now
        if current >= total:
            print()

# ---------- User-session fallback sender ----------
async def send_with_user_session(dest, path: Path, phone: str, user_session_string: str, api_id: int, api_hash: str):
    """
    Use a user session to send the document to dest.
    Prefer session string if provided; falling back to phone session if needed.
    This function starts a temporary user client (async context), sends, then stops it.
    """
    if not user_session_string and not phone:
        raise RuntimeError("phone or user_session_string required for user fallback but not provided.")

    client_args = {
        "api_id": api_id,
        "api_hash": api_hash,
        "parse_mode": enums.ParseMode.DEFAULT,
        "no_updates": True,
    }

    # choose session identifier for Client constructor
    if user_session_string:
        # when session_string passed as keyword to Client, use parameter name 'session_string'
        # Client accepts session_name or session_string; pass it as first positional arg is fine.
        # We'll pass session string as `session_string=...`
        async with Client(
            session_name="user_session",
            session_string=user_session_string,
            **client_args
        ) as user:
            try:
                print("User fallback: sending file as a user (session string)...")
                total = path.stat().st_size
                prog = ProgressPrinter(total)
                sent = await user.send_document(
                    chat_id=dest,
                    document=str(path),
                    caption=f"File delivered to owner ({path.name})",
                    disable_notification=True,
                    progress=prog.callback,
                    force_document=True
                )
                mid = getattr(sent, "message_id", getattr(sent, "id", None))
                print("User session: send OK. message id:", mid)
                return True
            except Exception as e:
                print("User session fallback failed (session string):", type(e).__name__, e)
                return False
    else:
        # fallback to phone login session (interactive, may not be suitable in headless environments)
        async with Client(
            session_name="user_phone_session",
            phone_number=phone,
            **client_args
        ) as user:
            try:
                print("User fallback: sending file as a user (phone login)...")
                total = path.stat().st_size
                prog = ProgressPrinter(total)
                sent = await user.send_document(
                    chat_id=dest,
                    document=str(path),
                    caption=f"File delivered to owner ({path.name})",
                    disable_notification=True,
                    progress=prog.callback,
                    force_document=True
                )
                mid = getattr(sent, "message_id", getattr(sent, "id", None))
                print("User session: send OK. message id:", mid)
                return True
            except Exception as e:
                print("User session fallback failed (phone):", type(e).__name__, e)
                return False

# ---------- Async main ----------
async def main(args):
    file_path = Path(args.file)
    if not file_path.exists():
        print("ERROR: file not found:", file_path.resolve())
        return 2

    api_id = args.api_id or API_ID
    api_hash = args.api_hash or API_HASH
    bot_token = args.bot_token or BOT_TOKEN
    user_session_string = args.user_session_string or USER_SESSION_STRING
    phone_number = args.phone or PHONE_NUMBER

    if api_id == 0 or not api_hash:
        print("ERROR: API_ID and API_HASH must be set either in env or via --api-id/--api-hash.")
        return 2
    if not bot_token:
        print("ERROR: BOT_TOKEN must be set either in env or via --bot-token.")
        return 2

    owner = args.owner
    dest = owner
    if isinstance(dest, str):
        dest_str = dest.strip()
        if dest_str.lstrip("-").isdigit():
            try:
                dest = int(dest_str)
            except Exception:
                pass

    # Detect premium only if user session string provided
    IS_PREMIUM_USER = False
    if user_session_string:
        # Start a temporary user client to check premium status, then close it
        try:
            async with Client(session_name="user_check_premium", session_string=user_session_string,
                              api_id=api_id, api_hash=api_hash, parse_mode=enums.ParseMode.DEFAULT, no_updates=True) as user_check:
                me = await user_check.get_me()
                IS_PREMIUM_USER = bool(getattr(me, "is_premium", False))
                print("User session detected. premium:", IS_PREMIUM_USER)
        except Exception as e:
            print("Could not start user client to detect premium (continuing):", type(e).__name__, e)
            IS_PREMIUM_USER = False
    else:
        print("Using 2GB split support (non-premium or no user session).")

    MAX_SPLIT_SIZE = 4194304000 if IS_PREMIUM_USER else 2097152000
    if IS_PREMIUM_USER:
        print("Enabled 4GB split support for premium user.")

    # Start bot client with async with
    session_name = "send_owner_bot"
    bot_client = Client(session_name, api_id=api_id, api_hash=api_hash, bot_token=bot_token, parse_mode=enums.ParseMode.DEFAULT)

    try:
        async with bot_client as bot:
            # get bot identity
            try:
                me = await bot.get_me()
                print("Bot identity:", getattr(me, "username", None), f"(id={me.id})")
            except Exception as e:
                print("Warning: couldn't get bot identity:", type(e).__name__, e)

            # Test sending small message
            try:
                print("Testing bot->owner permission with a small text message...")
                test = await bot.send_message(dest, "Test message from bot (this will be deleted).")
                mid = getattr(test, "message_id", getattr(test, "id", None))
                print("Bot can message owner. test message id:", mid)
                try:
                    await bot.delete_messages(dest, mid)
                    print("Test message deleted.")
                except Exception:
                    pass
            except UserIsBot:
                print("ERROR: target is a bot account (USER_IS_BOT). Bot cannot message another bot.")
                if phone_number or user_session_string:
                    print("Trying user fallback to message the bot account...")
                    ok = await send_with_user_session(dest, file_path, phone_number, user_session_string, api_id, api_hash)
                    if ok:
                        print("Sent via user session.")
                        return 0
                return 4
            except PeerIdInvalid:
                print("PeerIdInvalid: bot cannot access this user (owner probably hasn't started the bot).")
                if phone_number or user_session_string:
                    print("Attempting user-session fallback (since bot cannot message owner)...")
                    ok = await send_with_user_session(dest, file_path, phone_number, user_session_string, api_id, api_hash)
                    if ok:
                        print("Fallback succeeded via user session.")
                        return 0
                    else:
                        print("Fallback failed. Ask the owner to open a chat with the bot and run /start.")
                        return 5
                else:
                    print("No phone number or user-session-string for fallback. Ask the owner to open a chat with the bot and run /start.")
                    return 5
            except Forbidden:
                print("Forbidden: bot is not allowed to send messages to the owner (owner may have blocked the bot).")
                if phone_number or user_session_string:
                    print("Attempting user-session fallback despite Forbidden...")
                    ok = await send_with_user_session(dest, file_path, phone_number, user_session_string, api_id, api_hash)
                    if ok:
                        print("Fallback via user succeeded.")
                        return 0
                return 6
            except RPCError as e:
                print("RPCError during test send:", type(e).__name__, e)
                if phone_number or user_session_string:
                    print("Trying user fallback due to RPCError...")
                    ok = await send_with_user_session(dest, file_path, phone_number, user_session_string, api_id, api_hash)
                    if ok:
                        print("Fallback via user succeeded.")
                        return 0
                return 7

            # If test message succeeded, proceed to send document
            print("Sending document to owner via bot...")
            total = file_path.stat().st_size
            prog = ProgressPrinter(total)
            try:
                doc = await bot.send_document(
                    chat_id=dest,
                    document=str(file_path),
                    caption=f"File for owner: {file_path.name}",
                    disable_notification=True,
                    progress=prog.callback,
                    force_document=True
                )
                doc_mid = getattr(doc, "message_id", getattr(doc, "id", None))
                print("Bot send_document succeeded. message id:", doc_mid)
                return 0
            except UserIsBot:
                print("Target is a bot account (USER_IS_BOT). Aborting bot send. Trying user fallback if provided.")
                if phone_number or user_session_string:
                    ok = await send_with_user_session(dest, file_path, phone_number, user_session_string, api_id, api_hash)
                    if ok:
                        print("User fallback delivered the file.")
                        return 0
                return 8
            except PeerIdInvalid:
                print("PeerIdInvalid while sending document: bot lost access unexpectedly.")
                if phone_number or user_session_string:
                    print("Trying user fallback to deliver the file...")
                    ok = await send_with_user_session(dest, file_path, phone_number, user_session_string, api_id, api_hash)
                    if ok:
                        print("Fallback delivered the file.")
                        return 0
                    else:
                        print("Fallback failed.")
                        return 9
                else:
                    print("Provide phone number or user-session-string to enable user-session fallback.")
                    return 9
            except Forbidden:
                print("Forbidden: bot cannot send document to the owner (blocked).")
                if phone_number or user_session_string:
                    ok = await send_with_user_session(dest, file_path, phone_number, user_session_string, api_id, api_hash)
                    if ok:
                        print("Fallback delivered the file.")
                        return 0
                return 10
            except FloodWait as fw:
                print("FloodWait:", fw.value, "seconds. Sleeping...")
                await asyncio.sleep(fw.value)
                return 11
            except RPCError as e:
                print("RPCError while sending document:", type(e).__name__, e)
                if phone_number or user_session_string:
                    print("Attempting user fallback due to RPCError...")
                    ok = await send_with_user_session(dest, file_path, phone_number, user_session_string, api_id, api_hash)
                    if ok:
                        print("Fallback succeeded.")
                        return 0
                return 12

    except Exception as e:
        print("Failed to start bot client or an unexpected error occurred:", type(e).__name__, e)
        return 20

# ---------- CLI ----------
def build_argparser():
    p = argparse.ArgumentParser(prog="main.py", description="Send a file to a Telegram user via bot with optional user fallback.")
    p.add_argument("--file", "-f", required=True, help="Path to file to send.")
    p.add_argument("--owner", "-o", required=True, help="Owner id (numeric) or @username to send file to.")
    p.add_argument("--api-id", type=int, default=0, help="Telegram API ID (overrides env API_ID).")
    p.add_argument("--api-hash", default="", help="Telegram API Hash (overrides env API_HASH).")
    p.add_argument("--bot-token", default="", help="Bot token (overrides env BOT_TOKEN).")
    p.add_argument("--phone", default="", help="Phone number for user fallback (if needed).")
    p.add_argument("--user-session-string", "-us", default="", help="User session string for fallback (overrides env USER_SESSION_STRING).")
    return p

if __name__ == "__main__":
    parser = build_argparser()
    args = parser.parse_args()
    # Run the async main
    exit_code = asyncio.run(main(args))
    sys.exit(exit_code if isinstance(exit_code, int) else 0)
