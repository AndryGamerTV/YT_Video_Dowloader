from flask import Flask, render_template, request, jsonify, send_file, make_response, after_this_request
import yt_dlp
import os
import time
from urllib.parse import quote

app = Flask(__name__)

# Папка нужна для временной склейки, но файлы там храниться не будут
DOWNLOAD_FOLDER = 'downloads'
if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/get-video-info', methods=['POST'])
def get_video_info():
    data = request.json
    url = data.get('url')
    if not url:
        return jsonify({'error': 'URL не вказано'}), 400

    try:
        ydl_opts = {'quiet': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            formats = info.get('formats', [])
            available_resolutions = set()

            for f in formats:
                if f.get('vcodec') != 'none' and f.get('height'):
                    available_resolutions.add(f['height'])
            
            sorted_res = sorted(list(available_resolutions), reverse=True)

            return jsonify({
                'title': info.get('title'),
                'thumbnail': info.get('thumbnail'),
                'duration': info.get('duration_string'),
                'resolutions': sorted_res
            })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/download', methods=['POST'])
def download_video():
    data = request.json
    url = data.get('url')
    mode = data.get('mode', 'video')
    resolution = data.get('resolution')
    bitrate = data.get('bitrate', '192')

    try:
        timestamp = int(time.time())
        temp_filename = f"temp_{timestamp}" 

        ydl_opts = {
            'outtmpl': os.path.join(DOWNLOAD_FOLDER, f'{temp_filename}.%(ext)s'),
            'quiet': True,
            'overwrites': True,
            'restrictfilenames': True, 
        }

        if mode == 'audio':
            ydl_opts.update({
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': bitrate,
                }],
            })
        else:
            ydl_opts['merge_output_format'] = 'mp4'
            if not resolution or resolution == 'best':
                 ydl_opts['format'] = 'bestvideo+bestaudio/best'
            else:
                ydl_opts['format'] = f'bestvideo[height={resolution}]+bestaudio/best[height={resolution}]'

        # Скачивание
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)
            
        real_title = info_dict.get('title', 'video_download')
        ext = 'mp3' if mode == 'audio' else 'mp4'
        file_path = os.path.join(DOWNLOAD_FOLDER, f"{temp_filename}.{ext}")

        if not os.path.exists(file_path):
             return jsonify({'error': 'Ошибка создания файла'}), 500

        # --- ЧИСТКА ФАЙЛОВ ---
        # Эта функция сработает СРАЗУ ПОСЛЕ отправки файла пользователю
        @after_this_request
        def remove_file(response):
            try:
                os.remove(file_path)
                print(f"Файл удален: {file_path}")
            except Exception as error:
                print(f"Ошибка удаления файла: {error}")
            return response
        # ---------------------

        safe_filename = f"{real_title}.{ext}"
        encoded_filename = quote(safe_filename)

        response = make_response(send_file(file_path, as_attachment=True))
        response.headers["Content-Disposition"] = f"attachment; filename*=UTF-8''{encoded_filename}"
        return response

    except Exception as e:
        print(f"Server Error: {e}")
        return jsonify({'error': f"Ошибка: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(debug=True)