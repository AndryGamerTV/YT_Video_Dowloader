from flask import Flask, render_template, request, jsonify, send_file
import yt_dlp
import os
import time

app = Flask(__name__)

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
        return jsonify({'error': 'URL не предоставлен'}), 400

    try:
        ydl_opts = {'quiet': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            # --- ЛОГИКА ПОЛУЧЕНИЯ РАЗРЕШЕНИЙ ---
            formats = info.get('formats', [])
            available_resolutions = set()

            for f in formats:
                # Проверяем, что это видео (есть vcodec) и у него есть высота (height)
                if f.get('vcodec') != 'none' and f.get('height'):
                    available_resolutions.add(f['height'])
            
            # Сортируем от большего к меньшему (например: [1080, 720, 360])
            sorted_res = sorted(list(available_resolutions), reverse=True)
            # -----------------------------------

            return jsonify({
                'title': info.get('title'),
                'thumbnail': info.get('thumbnail'),
                'duration': info.get('duration_string'),
                'resolutions': sorted_res # Отправляем список на сайт
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
        ydl_opts = {
            'outtmpl': os.path.join(DOWNLOAD_FOLDER, '%(title)s.%(ext)s'),
            'quiet': True,
            'restrictfilenames': False,
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
            # Если выбрано "best" (Максимальное)
            if resolution == 'best' or not resolution:
                 ydl_opts['format'] = 'bestvideo+bestaudio/best'
            else:
                # Скачиваем конкретное разрешение, которое выбрал пользователь
                # Мы точно знаем, что оно существует, так как взяли его из списка
                ydl_opts['format'] = f'bestvideo[height={resolution}]+bestaudio/best[height={resolution}]'

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename_abspath = ydl.prepare_filename(info)
            
            if mode == 'audio':
                base, _ = os.path.splitext(filename_abspath)
                filename_abspath = base + '.mp3'

        final_filename = os.path.basename(filename_abspath)

        return send_file(
            filename_abspath, 
            as_attachment=True, 
            download_name=final_filename 
        )

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'error': f"Ошибка загрузки: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(debug=True)