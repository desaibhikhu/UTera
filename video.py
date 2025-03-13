import requests
import aria2p
from datetime import datetime
from status import format_progress_bar
import aiohttp
import os, time
import logging
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton


import os
import aiohttp
import aiofiles
import aria2p
import random
import asyncio
import logging
import requests
import time
from datetime import datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

# Terabox API Details
TERABOX_API_URL = "https://terabox.web.id"
TERABOX_API_TOKEN = "Brenner02"
THUMBNAIL = "https://envs.sh/S-T.jpg"

# Aria2 Configuration
aria2 = aria2p.API(
    aria2p.Client(
        host="http://localhost",
        port=6800,
        secret=""
    )
)

aria2.set_global_options({
    "max-tries": "50",
    "retry-wait": "3",
    "continue": "true"
})

async def fetch_json(url: str) -> dict:
    """Fetch JSON data from a URL."""
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            return await resp.json()


async def download(url: str, user_id: int, filename: str, reply_msg, user_mention, file_size: int) -> str:
    sanitized_filename = filename.replace("/", "_").replace("\\", "_")
    file_path = os.path.join(os.getcwd(), sanitized_filename)

    options = {
        "out": sanitized_filename,
        "dir": os.getcwd(),
        "max-connection-per-server": "16",
        "split": "16",
        "continue": "true",
        "check-integrity": "true",
    }

    logging.info(f"Starting Aria2 download: {filename}")
    download = aria2.add_uris([url], options=options)

    start_time = datetime.now()
    last_update_time = time.time()

    while not download.is_complete:
        download.update()
        if download.error_message:
            raise Exception(f"Download failed: {download.error_message}")

        percentage = (download.completed_length / file_size) * 100 if file_size else 0
        elapsed_time_seconds = (datetime.now() - start_time).total_seconds()
        speed = download.download_speed
        eta = (file_size - download.completed_length) / speed if speed > 0 else 0

        if time.time() - last_update_time > 2:
            progress_text = format_progress_bar(
                filename=filename,
                percentage=percentage,
                done=download.completed_length,
                total_size=file_size,
                status="Downloading",
                eta=eta,
                speed=speed,
                elapsed=elapsed_time_seconds,
                user_mention=user_mention,
                user_id=user_id,
                aria2p_gid=download.gid
            )
            try:
                await reply_msg.edit_text(progress_text)
                last_update_time = time.time()
            except Exception as e:
                logging.warning(f"Error updating progress message: {e}")

        await asyncio.sleep(2)

    if download.is_complete:
        return file_path
    else:
        raise Exception("Download failed or was interrupted.")

async def download_video(url, reply_msg, user_mention, user_id, max_retries=3):
    try:
        logging.info(f"Fetching video info: {url}")

        # Fetch video details
        api_response = await fetch_json(f"{TERABOX_API_URL}/url?url={url}&token={TERABOX_API_TOKEN}")

        if not api_response or not isinstance(api_response, list) or "filename" not in api_response[0]:
            raise Exception("Invalid API response format.")

        # Extract details from response
        data = api_response[0]
        download_link = data["link"] + f"&random={random.randint(1, 10)}"
        video_title = data["filename"]
        file_size = int(data.get("size", 0))  # Convert to int to ensure proper type
        thumb_url = THUMBNAIL  # Use default if missing

        logging.info(f"Downloading: {video_title} | Size: {file_size} bytes")

        if file_size == 0:
            raise Exception("Failed to get file size, download aborted.")

        # Retry logic for robustness
        for attempt in range(1, max_retries + 1):
            try:
                file_path = await asyncio.create_task(download(download_link, user_id, video_title, reply_msg, user_mention, file_size))
                break  # Exit loop if successful
            except Exception as e:
                logging.warning(f"Download failed (Attempt {attempt}/{max_retries}): {e}")
                if attempt == max_retries:
                    raise e  # Raise error if all retries fail
                await asyncio.sleep(3)

        # Send completion message
        await reply_msg.edit_text(f"✅ Download Complete!\n📂 {video_title}")
        return file_path, thumb_url, video_title, None  # No duration in response

    except Exception as e:
        logging.error(f"Error: {e}", exc_info=True)
        return None, None, None, None


async def upload_video(client, file_path, thumbnail_path, video_title, reply_msg, collection_channel_id, user_mention, user_id, message):
    file_size = os.path.getsize(file_path)
    uploaded = 0
    start_time = datetime.now()
    last_update_time = time.time()

    async def progress(current, total):
        nonlocal uploaded, last_update_time
        uploaded = current
        percentage = (current / total) * 100
        elapsed_time_seconds = (datetime.now() - start_time).total_seconds()

        speed = current / elapsed_time_seconds if elapsed_time_seconds > 0 else 0
        eta = (total - current) / speed if speed > 0 else 0

        if time.time() - last_update_time > 2:
            progress_text = format_progress_bar(
                filename=video_title,
                percentage=percentage,
                done=current,
                total_size=total,
                status="Uploading",
                eta=eta,
                speed=speed,
                elapsed=elapsed_time_seconds,
                user_mention=user_mention,
                user_id=user_id,
                aria2p_gid=""
            )
            try:
                await reply_msg.edit_text(progress_text)
                last_update_time = time.time()
            except Exception as e:
                logging.warning(f"Error updating progress message: {e}")

    try:
        collection_message = await client.send_video(
            chat_id=collection_channel_id,
            video=file_path,
            caption=f"✨ {video_title}\n👤 ʟᴇᴇᴄʜᴇᴅ ʙʏ: {user_mention}\n📥 ᴜsᴇʀ ʟɪɴᴋ: tg://user?id={user_id}",
            thumb=thumbnail_path,
            progress=progress
        )

        await client.copy_message(
            chat_id=message.chat.id,
            from_chat_id=collection_channel_id,
            message_id=collection_message.id
        )

        await asyncio.sleep(1)
        await message.delete()

        await reply_msg.delete()
        sticker_message = await message.reply_sticker("CAACAgIAAxkBAAEZdwRmJhCNfFRnXwR_lVKU1L9F3qzbtAAC4gUAAj-VzApzZV-v3phk4DQE")
        await asyncio.sleep(5)
        await sticker_message.delete()

    except FloodWait as e:
        logging.warning(f"FloodWait triggered: Sleeping for {e.value} seconds")
        await asyncio.sleep(e.value)
        return await upload_video(client, file_path, thumbnail_path, video_title, reply_msg, collection_channel_id, user_mention, user_id, message)  # Retry

    except Exception as e:
        logging.error(f"Upload failed: {e}", exc_info=True)
        await reply_msg.edit_text(f"❌ Upload failed: {e}")

    finally:
        if os.path.exists(file_path):
            os.remove(file_path)
        if os.path.exists(thumbnail_path):
            os.remove(thumbnail_path)

    return collection_message.id
