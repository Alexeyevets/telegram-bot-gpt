import os
import subprocess
import logging
import re
import requests
from PIL import Image
from io import BytesIO
from telegram import Update, InputFile
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
import yt_dlp as youtube_dl
from user_manager import is_user_blocked, add_user
from user_database import get_user_by_id, increment_request_count, check_and_reset_request_counts

logger = logging.getLogger(__name__)

SPONSORBLOCK_API_URL = "https://sponsor.ajay.app/api/skipSegments?videoID={}"

YOUTUBE_URL_PATTERN = re.compile(
    r'(https?://)?(www\.)?(youtube|youtu|youtube-nocookie)\.(com|be)/.+')

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id
    nickname = update.message.from_user.full_name
    username = update.message.from_user.username

    if not is_user_blocked(user_id):
        add_user(user_id, nickname, username)
        await update.message.reply_text('Привет! Отправь мне ссылку на YouTube видео, и я скачаю аудио из него.')

async def download_audio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id
    if is_user_blocked(user_id):
        return

    user = get_user_by_id(user_id)
    if not user:
        nickname = update.message.from_user.full_name
        await update.message.reply_text(f'{nickname}, к сожалению, вы ещё не авторизованы. Нажмите /start для пользования ботом, спасибо!')
        return

    message_text = update.message.text
    url = extract_youtube_url(message_text)

    if not url:
        await update.message.reply_text('Пожалуйста, отправьте ссылку на видео YouTube.')
        return

    waiting_message = await update.message.reply_text('_Скачиваю аудио, пожалуйста подождите..._', parse_mode=ParseMode.MARKDOWN)

    ydl_opts = {
        'format': 'bestaudio[ext=m4a]',
        'outtmpl': '%(title)s.%(ext)s',
    }

    try:
        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)
            audio_file = ydl.prepare_filename(info_dict)
            video_title = info_dict.get('title', 'Audio')
            video_uploader = info_dict.get('uploader', 'Unknown')
            thumbnail_url = info_dict.get('thumbnail')

        video_id = info_dict.get('id')
        ad_segments = get_ad_segments(video_id)

        if ad_segments:
            logger.info(f"Получены таймкоды рекламы: {ad_segments}")
            audio_file = remove_ad_segments(audio_file, ad_segments)

        thumbnail_file = None
        if thumbnail_url:
            thumbnail_file = await download_and_process_thumbnail(thumbnail_url)

        file_size = os.path.getsize(audio_file)
        max_size = 50 * 1024 * 1024  # 50 MB in bytes

        if file_size > max_size:
            await split_audio_file(audio_file, max_size, update, context, video_title, video_uploader, thumbnail_file)
        else:
            audio_file_with_thumbnail = embed_thumbnail_into_audio(audio_file, thumbnail_file, video_title, video_uploader)
            await send_audio_with_thumbnail(update, context, audio_file_with_thumbnail, video_title, video_uploader, thumbnail_file)
            if os.path.exists(audio_file_with_thumbnail):
                os.remove(audio_file_with_thumbnail)
        
    except Exception as e:
        await update.message.reply_text(f'Произошла ошибка: {e}')
        logger.error(f'Ошибка при обработке видео: {e}')
    
    finally:
        await waiting_message.delete()
        if os.path.exists(audio_file):
            os.remove(audio_file)
        if thumbnail_file and os.path.exists(thumbnail_file):
            os.remove(thumbnail_file)

async def send_audio_with_thumbnail(update, context, audio_file, video_title, video_uploader, thumbnail_file):
    """Send audio file with thumbnail to Telegram."""
    try:
        logger.info("Отправка аудиофайла с обложкой")
        files = {
            'audio': open(audio_file, 'rb'),
            'thumb': open(thumbnail_file, 'rb') if thumbnail_file else None
        }
        data = {
            'chat_id': update.message.chat_id,
            'title': video_title,
            'performer': video_uploader,
            'audio': 'attach://audio'
        }
        if files['thumb']:
            data['thumb'] = 'attach://thumb'
        
        response = requests.post(
            url=f"https://api.telegram.org/bot{context.bot.token}/sendAudio",
            data=data,
            files=files
        )
        
        logger.info(f"Ответ от Telegram: {response.json()}")
        for file in files.values():
            if file:
                file.close()
    except Exception as e:
        logger.error(f"Ошибка при отправке аудиофайла: {e}")
        raise e

def get_ad_segments(video_id):
    """Получение сегментов рекламы с помощью API SponsorBlock."""
    try:
        response = requests.get(SPONSORBLOCK_API_URL.format(video_id))
        response.raise_for_status()
        segments = response.json()
        ad_segments = [segment['segment'] for segment in segments if segment['category'] == 'sponsor']
        return ad_segments
    except Exception as e:
        logger.error(f"Ошибка при получении сегментов рекламы: {e}")
        return []

def remove_ad_segments(audio_file, ad_segments):
    """Удаление рекламных сегментов из аудиофайла."""
    input_file = audio_file
    base_name = os.path.splitext(audio_file)[0]
    segment_files = []

    initial_offset = 0  # Смещение начального сегмента

    if ad_segments and ad_segments[0][0] == 0:
        start, end = ad_segments.pop(0)
        initial_offset = end
        temp_file = f"{base_name}_temp.m4a"
        command = [
            "ffmpeg", "-i", input_file, "-ss", str(end), "-c", "copy", temp_file
        ]
        try:
            logger.info(f"Выполняется команда: {' '.join(command)}")
            subprocess.run(command, check=True)
            input_file = temp_file
        except subprocess.CalledProcessError as e:
            logger.error(f"Ошибка выполнения команды: {e}")

    ad_segments = [(start - initial_offset, end - initial_offset) for start, end in ad_segments]

    last_end = 0
    for i, (start, end) in enumerate(ad_segments):
        if start <= last_end:
            continue
        
        if last_end < start:
            segment_file = f"{base_name}_segment_{i}.m4a"
            segment_files.append(segment_file)
            command = [
                "ffmpeg", "-i", input_file, "-ss", str(last_end), "-to", str(start),
                "-c", "copy", segment_file
            ]
            try:
                logger.info(f"Выполняется команда: {' '.join(command)}")
                subprocess.run(command, check=True)
            except subprocess.CalledProcessError as e:
                logger.error(f"Ошибка выполнения команды: {e}")

        last_end = end

    final_segment_file = f"{base_name}_segment_final.m4a"
    command = [
        "ffmpeg", "-i", input_file, "-ss", str(last_end), "-c", "copy", final_segment_file
    ]
    try:
        logger.info(f"Выполняется команда: {' '.join(command)}")
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as e:
        logger.error(f"Ошибка выполнения команды: {e}")

    segment_files.append(final_segment_file)

    with open(f"{base_name}_filelist.txt", "w") as f:
        for segment_file in segment_files:
            f.write(f"file '{os.path.abspath(segment_file)}'\n")

    output_file = "cleaned_" + audio_file
    command = [
        "ffmpeg", "-f", "concat", "-safe", "0", "-i", f"{base_name}_filelist.txt",
        "-c", "copy", output_file
    ]
    try:
        logger.info(f"Выполняется команда: {' '.join(command)}")
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as e:
        logger.error(f"Ошибка выполнения команды: {e}")

    for segment_file in segment_files:
        os.remove(segment_file)
    os.remove(f"{base_name}_filelist.txt")

    if os.path.exists(output_file):
        os.remove(input_file)
        return output_file
    else:
        return input_file

async def split_audio_file(audio_file, max_size, update, context, video_title, video_uploader, thumbnail_file):
    """Функция для разделения аудиофайла на части."""
    base_name = os.path.splitext(audio_file)[0]
    total_duration = get_audio_duration(audio_file)
    num_segments = -(-os.path.getsize(audio_file) // max_size)  # округление вверх
    segment_duration = total_duration / num_segments

    command = [
        'ffmpeg', '-i', audio_file, '-f', 'segment', '-segment_time', str(segment_duration),
        '-c', 'copy', f'{base_name}_part_%03d.m4a'
    ]
    logger.info(f"Выполняется команда: {' '.join(command)}")
    subprocess.run(command, check=True)

    part_files = [f for f in os.listdir() if f.startswith(f'{base_name}_part_') and f.endswith('.m4a')]
    part_files.sort()

    for part_file in part_files:
        part_file_with_thumbnail = embed_thumbnail_into_audio(part_file, thumbnail_file, video_title, video_uploader)
        await send_audio_with_thumbnail(update, context, part_file_with_thumbnail, video_title, video_uploader, thumbnail_file)
        
        # Удаляем временные файлы после их обработки
        if os.path.exists(part_file_with_thumbnail):
            os.remove(part_file_with_thumbnail)
        if os.path.exists(part_file):
            os.remove(part_file)

    if os.path.exists(audio_file):
        os.remove(audio_file)

    if thumbnail_file and os.path.exists(thumbnail_file):
        os.remove(thumbnail_file)

def get_audio_duration(audio_file):
    """Функция для получения продолжительности аудиофайла."""
    command = [
        'ffprobe', '-v', 'error', '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1', audio_file
    ]
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return float(result.stdout)

def extract_youtube_url(text):
    """Извлечение ссылки на YouTube из текста."""
    match = YOUTUBE_URL_PATTERN.search(text)
    return match.group(0) if match else None

async def download_and_process_thumbnail(thumbnail_url):
    """Скачивание и обработка эскиза."""
    try:
        response = requests.get(thumbnail_url)
        response.raise_for_status()
        img = Image.open(BytesIO(response.content))
        img = img.convert("RGB")
        img.thumbnail((320, 320))
        thumbnail_file = "thumbnail.jpg"
        img.save(thumbnail_file, "JPEG", quality=85)
        if os.path.getsize(thumbnail_file) > 200 * 1024:  # если размер больше 200 kB
            img.save(thumbnail_file, "JPEG", quality=75)
        logger.info(f"Эскиз успешно скачан и обработан: {thumbnail_file}")
        return thumbnail_file
    except Exception as e:
        logger.error(f"Ошибка при скачивании и обработке эскиза: {e}")
        return None

def embed_thumbnail_into_audio(audio_file, thumbnail_file, title, performer):
    """Встраивание эскиза в аудиофайл."""
    if not thumbnail_file:
        logger.info("Обложка не предоставлена, пропуск встраивания обложки.")
        return audio_file

    output_file = f"thumbnail_{audio_file}"
    command = [
        "ffmpeg", "-i", audio_file, "-i", thumbnail_file, "-map", "0", "-map", "1", "-c", "copy",
        "-metadata", f"title={title}", "-metadata", f"artist={performer}", "-disposition:v", "attached_pic",
        output_file
    ]
    try:
        logger.info(f"Выполняется команда: {' '.join(command)}")
        subprocess.run(command, check=True)
        logger.info(f"Эскиз успешно встроен в аудиофайл: {output_file}")
    except subprocess.CalledProcessError as e:
        logger.error(f"Ошибка выполнения команды: {e}")
        return audio_file
    
    return output_file
