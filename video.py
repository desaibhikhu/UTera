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

async def aria2_download(url: str, user_id: int, filename: str, reply_msg, user_mention) -> str:
    """Download using aria2 with parallel connections."""
    sanitized_filename = filename.replace("/", "_").replace("\\", "_")
    file_path = os.path.join(os.getcwd(), sanitized_filename)

    cookies = await fetch_json(f"{TERABOX_API_URL}/gc?token={TERABOX_API_TOKEN}")

    download_key = f"{user_id}-{sanitized_filename}"  # Unique key per file
    downloads_manager[download_key] = {"downloaded": 0}

    download = aria2.add_uris([url], options={"out": sanitized_filename})
    start_time = datetime.now()
    last_update_time = time.time()

    while not download.is_complete:
        download.update()
        percentage = download.progress
        done = download.completed_length
        total_size = download.total_length
        speed = download.download_speed
        eta = download.eta
        elapsed_time_seconds = (datetime.now() - start_time).total_seconds()

        if time.time() - last_update_time > 2:
            progress_text = (
                f"📥 Downloading: {filename}\n"
                f"🔹 Progress: {percentage:.2f}%\n"
                f"⚡ Speed: {speed / 1024 / 1024:.2f} MB/s\n"
                f"⏳ ETA: {eta}s\n"
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
    """Fetch video details and download using Aria2."""
    try:
        logging.info(f"Fetching video info: {url}")
        api_response = await fetch_json(f"{TERABOX_API_URL}/url?url={url}&token={TERABOX_API_TOKEN}")

        if not api_response or not isinstance(api_response, list) or "filename" not in api_response[0]:
            raise Exception("Invalid API response format.")

        # Extract details from response
        data = api_response[0]
        download_link = data["link"] + f"&random={random.randint(1, 10)}"
        video_title = data["filename"]
        file_size = int(data.get("size", 0))  # Convert to int to ensure proper type
        thumb_url = THUMBNAIL  # Use default if missing

        logging.info(f"Downloading: {video_title}")

        # Ensure at least one valid download link exists
        if not fast_download_link and not hd_download_link:
            raise ValueError("No valid download links found in API response.")

        try:
            if fast_download_link:
                file_path = await asyncio.create_task(aria2_download(fast_download_link, user_id, video_title, reply_msg, user_mention))
            else:
                file_path = await asyncio.create_task(aria2_download(hd_download_link, user_id, video_title, reply_msg, user_mention))
        except Exception as e:
            logging.warning(f"Fast Download failed, retrying with HD Video. Error: {e}")
            if hd_download_link:
                file_path = await asyncio.create_task(aria2_download(hd_download_link, user_id, video_title, reply_msg, user_mention))
            else:
                raise ValueError("Both Fast Download and HD Video links failed.")

        # Download thumbnail
        thumbnail_path = "thumbnail.jpg"
        thumb_response = requests.get(thumbnail_url)
        with open(thumbnail_path, "wb") as thumb_file:
            thumb_file.write(thumb_response.content)

        await reply_msg.edit_text("✅ Download Complete! Uploading...")

        return file_path, thumbnail_path, video_title

    except ValueError as ve:
        logging.error(f"Invalid API Response: {ve}")
        await reply_msg.edit_text("⚠️ Unable to fetch video details. Please try again later.")
        return None, None, None

    except Exception as e:
        logging.error(f"Download error: {e}")

        buttons = []
        if "hd_download_link" in locals() and hd_download_link:
            buttons.append([InlineKeyboardButton("🚀 HD Video", url=hd_download_link)])
        if "fast_download_link" in locals() and fast_download_link:
            buttons.append([InlineKeyboardButton("⚡ Fast Download", url=fast_download_link)])

        if buttons:
            reply_markup = InlineKeyboardMarkup(buttons)
            await reply_msg.reply_text(
                "Fast Download Link is broken. Please use the manual download links below.",
                reply_markup=reply_markup
            )

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
