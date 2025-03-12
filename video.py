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
        
        response = requests.get(f"https://delta.terabox.web.id/url?url={url}&token={TERABOX_API_TOKEN}")
        response.raise_for_status()
        data = response.json()

        # Extract details
        resolutions = data["response"][0]["resolutions"]
        fast_download_link = resolutions["Fast Download"]
        hd_download_link = resolutions["HD Video"]
        thumbnail_url = data["response"][0]["thumbnail"]
        video_title = data["response"][0]["title"]

        logging.info(f"Downloading: {video_title}")

        try:
            file_path = await asyncio.create_task(aria2_download(fast_download_link, user_id, video_title, reply_msg, user_mention))
        except Exception as e:
            logging.warning(f"Fast Download failed, retrying with HD Video. Error: {e}")
            file_path = await asyncio.create_task(aria2_download(hd_download_link, user_id, video_title, reply_msg, user_mention))

        # Download thumbnail
        thumbnail_path = "thumbnail.jpg"
        thumb_response = requests.get(thumbnail_url)
        with open(thumbnail_path, "wb") as thumb_file:
            thumb_file.write(thumb_response.content)

        await reply_msg.edit_text("✅ Download Complete! Uploading...")

        return file_path, thumbnail_path, video_title

    except Exception as e:
        logging.error(f"Download error: {e}")
        buttons = [
            [InlineKeyboardButton("🚀 HD Video", url=hd_download_link)],
            [InlineKeyboardButton("⚡ Fast Download", url=fast_download_link)]
        ]
        reply_markup = InlineKeyboardMarkup(buttons)
        await reply_msg.reply_text(
            "Fast Download Link is broken. Please use the manual download links below.",
            reply_markup=reply_markup
        )
        return None, None, None

# async def download_video(url, reply_msg, user_mention, user_id):
#     response = requests.get(f"https://teraboxvideodownloader.nepcoderdevs.workers.dev/?url={url}")
#     response.raise_for_status()
#     data = response.json()

#     resolutions = data["response"][0]["resolutions"]
#     fast_download_link = resolutions["Fast Download"]
#     hd_download_link = resolutions["HD Video"]
#     thumbnail_url = data["response"][0]["thumbnail"]
#     video_title = data["response"][0]["title"]

#     download = aria2.add_uris([fast_download_link])
#     start_time = datetime.now()

#     while not download.is_complete:
#         download.update()
#         percentage = download.progress
#         done = download.completed_length
#         total_size = download.total_length
#         speed = download.download_speed
#         eta = download.eta
#         elapsed_time_seconds = (datetime.now() - start_time).total_seconds()
#         progress_text = format_progress_bar(
#             filename=video_title,
#             percentage=percentage,
#             done=done,
#             total_size=total_size,
#             status="Downloading",
#             eta=eta,
#             speed=speed,
#             elapsed=elapsed_time_seconds,
#             user_mention=user_mention,
#             user_id=user_id,
#             aria2p_gid=download.gid
#         )
#         await reply_msg.edit_text(progress_text)
#         await asyncio.sleep(2)

#     if download.is_complete:
#         file_path = download.files[0].path

#         thumbnail_path = "thumbnail.jpg"
#         thumbnail_response = requests.get(thumbnail_url)
#         with open(thumbnail_path, "wb") as thumb_file:
#             thumb_file.write(thumbnail_response.content)

#         await reply_msg.edit_text("ᴜᴘʟᴏᴀᴅɪɴɢ...")

#         return file_path, thumbnail_path, video_title
#     else:
#         return markup


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
