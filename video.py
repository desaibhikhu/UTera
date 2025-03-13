import requests
import aria2p
from datetime import datetime
from status import format_progress_bar
import asyncio
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

async def get_final_download_url(url, cookies):
    """Follow HTTP 302 redirection and return the final download URL, using cookies."""
    async with aiohttp.ClientSession(cookies=cookies) as session:
        async with session.get(url, allow_redirects=False) as resp:
            if resp.status == 302 and "Location" in resp.headers:
                return resp.headers["Location"]
            raise Exception("Failed to fetch the final download URL")

async def aria2_download(url: str, user_id: int, filename: str, reply_msg, user_mention, cookies) -> str:
    """Download using aria2 with parallel connections and show speed + ETA."""
    sanitized_filename = filename.replace("/", "_").replace("\\", "_")
    file_path = os.path.join(os.getcwd(), sanitized_filename)

    # Convert cookies dict to "key=value" format for aria2
    cookie_string = "; ".join([f"{k}={v}" for k, v in cookies.items()])

    download = aria2.add_uris(
        [url],
        options={
            "out": sanitized_filename,
            "header": [f"Cookie: {cookie_string}"]
        }
    )

    start_time = datetime.now()
    last_update_time = time.time()

    while not download.is_complete:
        download.update()
        percentage = download.progress
        done = download.completed_length
        total_size = download.total_length
        speed = download.download_speed
        eta = download.eta  # Estimated time remaining (seconds)

        if time.time() - last_update_time > 2:
            progress_text = (
                f"📥 Downloading: `{filename}`\n"
                f"🔹 Progress: `{percentage:.2f}%`\n"
                f"⚡ Speed: `{speed / 1024 / 1024:.2f} MB/s`\n"
                f"⏳ ETA: `{eta}s`\n"
            )
            try:
                await reply_msg.edit_text(progress_text)
                last_update_time = time.time()
            except Exception as e:
                logging.warning(f"Error updating progress message: {e}")

        await asyncio.sleep(2)

    if download.has_failed:
        raise Exception("Aria2 download failed!")

    return download.files[0].path

async def download_video(url, reply_msg, user_mention, user_id):
    """Fetch video details and download using Aria2, handling redirects and cookies."""
    try:
        logging.info(f"Fetching video info: {url}")
        api_response = await fetch_json(f"{TERABOX_API_URL}/url?url={url}&token={TERABOX_API_TOKEN}")

        if not api_response or not isinstance(api_response, list) or "filename" not in api_response[0]:
            raise Exception("Invalid API response format.")

        # Fetch cookies
        cookies = await fetch_json(f"{TERABOX_API_URL}/gc?token={TERABOX_API_TOKEN}")

        # Extract details from API response
        data = api_response[0]
        terabox_redirect_url = data["link"]

        # Get final download URL with cookies
        final_download_url = await get_final_download_url(terabox_redirect_url, cookies)

        video_title = data["filename"]
        thumb_url = THUMBNAIL  # Use default if missing

        logging.info(f"Final Download URL: {final_download_url}")
        logging.info(f"Downloading: {video_title}")

        # Start download with Aria2, passing cookies
        file_path = await asyncio.create_task(
            aria2_download(final_download_url, user_id, video_title, reply_msg, user_mention, cookies)
        )

        # Download thumbnail
        thumbnail_path = "thumbnail.jpg"
        thumb_response = requests.get(thumb_url)
        with open(thumbnail_path, "wb") as thumb_file:
            thumb_file.write(thumb_response.content)

        await reply_msg.edit_text("✅ Download Complete! Uploading...")

        return file_path, thumbnail_path, video_title

    except Exception as e:
        logging.error(f"Download error: {e}")
        await reply_msg.edit_text("⚠️ Unable to fetch video details. Please try again later.")
        return None, None, None




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
        
        if time.time() - last_update_time > 2:
            progress_text = format_progress_bar(
                filename=video_title,
                percentage=percentage,
                done=current,
                total_size=total,
                status="Uploading",
                eta=(total - current) / (current / elapsed_time_seconds) if current > 0 else 0,
                speed=current / elapsed_time_seconds if current > 0 else 0,
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

    with open(file_path, 'rb') as file:
        collection_message = await client.send_video(
            chat_id=collection_channel_id,
            video=file,
            caption=f"✨ {video_title}\n👤 ʟᴇᴇᴄʜᴇᴅ ʙʏ : {user_mention}\n📥 ᴜsᴇʀ ʟɪɴᴋ: tg://user?id={user_id}",
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
    os.remove(file_path)
    os.remove(thumbnail_path)
    await asyncio.sleep(5)
    await sticker_message.delete()
    return collection_message.id
