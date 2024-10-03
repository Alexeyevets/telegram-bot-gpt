import os
import requests
from PIL import Image
from io import BytesIO
import subprocess

def download_thumbnail(video_id, output_dir="thumbnails"):
    """Скачивает превью видео с YouTube и сохраняет его в указанной директории."""
    url = f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg"
    response = requests.get(url)
    response.raise_for_status()

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    thumbnail_path = os.path.join(output_dir, f"{video_id}.jpg")
    with open(thumbnail_path, 'wb') as f:
        f.write(response.content)

    return thumbnail_path

def add_thumbnail_to_audio(audio_file, thumbnail_path):
    """Добавляет превью к аудиофайлу."""
    output_file = f"with_thumbnail_{audio_file}"
    command = [
        "ffmpeg", "-i", audio_file, "-i", thumbnail_path, "-map", "0", "-map", "1",
        "-c", "copy", "-disposition:v", "attached_pic", output_file
    ]
    subprocess.run(command, check=True)
    return output_file

if __name__ == "__main__":
    import sys
    video_id = sys.argv[1]
    audio_file = sys.argv[2]
    
    thumbnail_path = download_thumbnail(video_id)
    output_file = add_thumbnail_to_audio(audio_file, thumbnail_path)
    
    print(f"Thumbnail added to audio file: {output_file}")
