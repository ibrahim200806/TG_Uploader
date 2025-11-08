#!/usr/bin/env python3
"""
send.py

Send a file to a Telegram user using a bot, with optional user-session fallback.
Features:
 - CLI via argparse: --file, --owner, optional --phone, --user-session-string
 - Owner accepts numeric id or @username
 - If USER_SESSION_STRING is provided and the user account is Premium, enable 4GB split support
 - Keeps user_client available globally when started via session string
"""

import os
import sys
import time
import asyncio
import argparse
from pathlib import Path

# Pyrogram and errors
from pyrogram import Client
from pyrogram.errors import (
    Forbidden, PeerIdInvalid, RPCError, FloodWait, UserIsBot
)

# used for detecting premium
from pyrogram import enums

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
        # throttle updates to not spam terminal
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


# ---------- Utility: start a user client either from session string or from phone ----------
async def start_user_client_from_session_string(session_string: str, api_id: int, api_hash: str):
    """
    Starts a pyrogram client from a session string. Returns client instance or None.
    This is synchronous-start style to mirror .start() usage in existing code.
    """
    if not session_string:
        return None
    try:
        client = Client(
            "send_user_session",
            api_id=api_id,
            api_hash=api_hash,
            session_string=session_string,
            parse_mode=enums.ParseMode.DEFAULT,
            no_updates=True,
        )
        client.start()
        return client
    except Exception as e:
        print("Failed to start user client from session string:", type(e).__name__, e)
        return None


async def start_user_client_from_phone(phone: str, api_id: int, api_hash: str):
    """
    Starts a pyrogram client that will attempt login via the phone flow.
    Note: This function expects that the environment is interactive (for code).
    For automation, prefer session string.
    """
    if not phone:
        return None
    try:
        client = Client(
            "send_user_phone",
            api_id=api_id,
            api_hash=api_hash,
            phone_number=phone,
            parse_mode=enums.ParseMode.DEFAULT,
            no_updates=True,
        )
        client.start()
        return client
    except Exception as e:
        print("Failed to start user client via phone:", type(e).__name__, e)
        return None


# ---------- Main sending logic ----------
async def send_with_user_session(dest, path: Path, phone: str, user_client_session_string: str, api_id: int, api_hash: str):
    """
    Try to use a user session to send the document to dest.
    Prefer starting from session string if present; otherwise phone.
    Returns True on success, False otherwise.
    """
    client = None
    started_here = False
    try:
        if user_client_session_string:
            # start user client from session string (synchronous start for compatibility)
            client = await start_user_client_from_session_string(user_client_session_string, api_id, api_hash)
            started_here = True
        elif phone:
            client = await start_user_client_from_phone(phone, api_id, api_hash)
            started_here = True

        if client is None:
            raise RuntimeError("No user session available for fallback.")

        print("User fallback: sending file as a user...")
        total = path.stat().st_size
        prog = ProgressPrinter(total)
        sent = client.send_document(
            chat_id=dest,
            document=str(path),
            caption=f"File delivered to owner ({path.name})",
            disable_notification=True,
            progress=prog.callback,
            force_document=True
        )
        # pyrogram send_document returns message (synchronous when client not awaited)
        mid = getattr(sent, "message_id", getattr(sent, "id", None))
        print("User session: send OK. message id:", mid)
        return True
    except Exception as e:
        print("User session fallback failed:", type(e).__name__, e)
        return False
    finally:
        # if we started a client just for fallback, stop it
        try:
            if started_here and client:
                client.stop()
        except Exception:
            pass


async def main(args):
    # validate inputs
    file_path = Path(args.file)
    if not file_path.exists():
        print("ERROR: file not found:", file_path.resolve())
        return 2

    # read configuration (prefer CLI args over env)
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

    owner = args.owner  # can be username '@user' or numeric id

    # Setup premium detection defaults
    IS_PREMIUM_USER = False
    user_client = None

    # If session string present, start a user client and detect premium
    if user_session_string:
        print("Starting user client from session string to detect premium status...")
        user_client = await start_user_client_from_session_string(user_session_string, api_id, api_hash)
        if user_client:
            try:
                IS_PREMIUM_USER = bool(getattr(user_client.get_me(), "is_premium", False))
                print("User is premium:", IS_PREMIUM_USER)
            except Exception:
                # try accessing attribute via client.me if get_me() isn't desired
                try:
                    IS_PREMIUM_USER = bool(getattr(user_client.me, "is_premium", False))
                    print("User is premium (via client.me):", IS_PREMIUM_USER)
                except Exception:
                    IS_PREMIUM_USER = False
        else:
            print("Could not start user client from session string.")

    # MAX_SPLIT_SIZE logic: if premium -> 4GB else 2GB
    # Use same constants as your prior code: 4194304000 and 2097152000 bytes.
    MAX_SPLIT_SIZE = 4194304000 if IS_PREMIUM_USER else 2097152000
    LEECH_SPLIT_SIZE = MAX_SPLIT_SIZE  # for this script we just set it equal
    if IS_PREMIUM_USER:
        print("Enabled 4GB split support for premium user.")
    else:
        print("Using 2GB split support (non-premium or no user session).")

    # --- Start bot client and try to send ---
    session_name = "send_owner_bot"
    bot = Client(session_name, api_id=api_id, api_hash=api_hash, bot_token=bot_token, parse_mode=enums.ParseMode.DEFAULT)

    try:
        bot.start()
    except Exception as e:
        print("Failed to start bot client:", type(e).__name__, e)
        # attempt to stop if partially started
        try:
            bot.stop()
        except Exception:
            pass
        return 3

    try:
        me = bot.get_me()
        print("Bot identity:", getattr(me, "username", None), f"(id={me.id})")
    except Exception as e:
        print("Warning: couldn't get bot identity:", type(e).__name__, e)

    dest = owner

    # if owner looks like a number string, try convert to int for some Pyrogram calls
    if isinstance(dest, str):
        dest_str = dest.strip()
        if dest_str.lstrip("-").isdigit():
            try:
                dest = int(dest_str)
            except Exception:
                pass  # leave as string
        # keep @username as-is

    # First try to send a small message to check whether bot can message the owner.
    try:
        print("Testing bot->owner permission with a small text message...")
        test = bot.send_message(dest, "Test message from bot (this will be deleted).")
        mid = getattr(test, "message_id", getattr(test, "id", None))
        print("Bot can message owner. test message id:", mid)
        try:
            bot.delete_messages(dest, mid)
            print("Test message deleted.")
        except Exception:
            # ignore delete errors
            pass
    except UserIsBot:
        print("ERROR: target is a bot account (USER_IS_BOT). Bot cannot message another bot.")
        # try fallback via user if provided
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
        # fallback not likely to help if blocked, but we still try user fallback
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
        doc = bot.send_document(
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
        print("FloodWait:", fw.value, "seconds. Sleeping (not recommended for CLI send).")
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
    finally:
        try:
            bot.stop()
        except Exception:
            pass
        # if we started user_client from session string and want to keep it running, we leave it.
        # For CLI send purpose, stop it to be tidy, unless user explicitly wanted to reuse it system-wide.
        try:
            if user_client:
                user_client.stop()
        except Exception:
            pass


# ---------- CLI ----------
def build_argparser():
    p = argparse.ArgumentParser(prog="send.py", description="Send a file to a Telegram user via bot with optional user fallback.")
    p.add_argument("--file", "-f", required=True, help="Path to file to send.")
    p.add_argument("--owner", "-o", required=True, help="Owner id (numeric) or @username to send file to.")
    p.add_argument("--api-id", type=int, default=0, help="Telegram API ID (overrides env API_ID).")
    p.add_argument("--api-hash", default="", help="Telegram API Hash (overrides env API_HASH).")
    p.add_argument("--bot-token", default="", help="Bot token (overrides env BOT_TOKEN).")
    p.add_argument("--phone", default="", help="Phone number for user fallback (if needed).")
    p.add_argument("--user-session-string", default="", help="User session string for fallback (overrides env USER_SESSION_STRING).")
    return p


if __name__ == "__main__":
    parser = build_argparser()
    args = parser.parse_args()
    # Basic validation: file exists (but main also checks)
    exit_code = asyncio.run(main(args))
    sys.exit(exit_code if isinstance(exit_code, int) else 0)
