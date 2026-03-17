from flask import Flask, render_template, request, session, jsonify
import io
import os
import base64
import random
import string
from captcha.image import ImageCaptcha

app = Flask(__name__, template_folder=os.path.join(os.path.dirname(__file__), 'templates'))
app.config['SECRET_KEY'] = '12345'
#app.config['UPLOAD_FOLDER'] = 'static/uploads'

def generate_captcha():
    """Генерирует картинку с капчей"""
    image = ImageCaptcha(width=200, height=60)
    # Генерируем случайный код из 6 символов
    captcha_text = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    data = image.generate(captcha_text)
    return captcha_text, data

@app.route('/debug_session')
def debug_session():
    """Показывает что хранится в сессии"""
    return f"Сессия: {session}<br>Капча: {session.get('captcha_answer', 'Нет')}"

def get_color_histogram(img):
    """Создаёт гистограмму цветов изображения"""
    import numpy as np

    img_array = np.array(img)

    # Если изображение чёрно-белое, превращаем в RGB
    if len(img_array.shape) == 2:
        img_array = np.stack([img_array] * 3, axis=-1)

    def reduce_hist(channel):
        hist = np.histogram(channel, bins=256, range=(0, 256))[0]
        # Усредняем каждые 16 значений
        reduced = []
        for i in range(0, 256, 16):
            reduced.append(int(np.mean(hist[i:i + 16])))
        return reduced

    return {
        'red': reduce_hist(img_array[:, :, 0]),
        'green': reduce_hist(img_array[:, :, 1]),
        'blue': reduce_hist(img_array[:, :, 2]),
        'labels': list(range(0, 256, 16))  # Метки для оси X
    }

@app.route('/')
def index():
    """Главная страница с капчей"""
    captcha_text, captcha_image = generate_captcha()
    # Кодируем картинку в base64 для отображения в HTML
    captcha_b64 = base64.b64encode(captcha_image.read()).decode('utf-8')
    session['captcha_answer'] = captcha_text

    return render_template('index.html', captcha_b64=captcha_b64)

@app.route('/refresh_captcha')
def refresh_captcha():
    """Обновляет капчу без перезагрузки страницы"""
    captcha_text, captcha_image = generate_captcha()
    session['captcha_answer'] = captcha_text
    captcha_b64 = base64.b64encode(captcha_image.read()).decode('utf-8')
    return jsonify({'captcha_b64': captcha_b64})


@app.route('/process', methods=['POST'])
def process():
    from PIL import Image, ImageDraw

    captcha_input = request.form.get('captcha_input')
    correct_answer = session.get('captcha_answer', '')

    # Для отладки - раскомментируй строку ниже
    print(f"Введено: {captcha_input}, Правильно: {correct_answer}")

    if not captcha_input:
        return jsonify({'error': 'Введите капчу!'}), 400

    if not correct_answer:
        return jsonify({'error': 'Сессия истекла. Обновите страницу.'}), 400

    if captcha_input.upper().strip() != correct_answer.upper().strip():
        return jsonify({'error': f'Неверная капча! (Введено: {captcha_input})'}), 400

    file = request.files.get('image')
    cross_type = request.form.get('cross_type')
    color = request.form.get('color')

    if not file:
        return jsonify({'error': 'Выберите изображение!'}), 400

    img = Image.open(file.stream)
    original_io = io.BytesIO()
    img.save(original_io, 'PNG')
    original_io.seek(0)
    original_b64 = base64.b64encode(original_io.read()).decode('utf-8')

    draw = ImageDraw.Draw(img)
    width, height = img.size

    if cross_type == 'vertical':
        draw.line((width // 2, 0, width // 2, height), fill=color, width=5)
        draw.line((width // 3, height // 2, width // 1.5, height // 2), fill=color, width=5)
    else:
        draw.line((0, height // 2, width, height // 2), fill=color, width=5)
        draw.line((width // 2, height // 3, width // 2, height // 1.5), fill=color, width=5)

    processed_io = io.BytesIO()
    img.save(processed_io, 'PNG')
    processed_io.seek(0)
    processed_b64 = base64.b64encode(processed_io.read()).decode('utf-8')

    return jsonify({
        'original_image': 'data:image/png;base64,' + original_b64,
        'processed_image': 'data:image/png;base64,' + processed_b64
    })

"""@app.route('/process', methods=['POST'])
def process():
    from PIL import Image, ImageDraw
    import io
    import base64

    captcha_input = request.form.get('captcha_input')
    correct_answer = session.get('captcha_answer', '')
    # Простая проверка (в реальном проекте нужно хранить в сессии)
    if not captcha_input or captcha_input.upper() != correct_answer.upper():
        return  jsonify({'error': 'Неверная капча! Попробуйте ещё раз.'}), 400

    # Получаем файл и тип креста
    file = request.files.get('image')
    cross_type = request.form.get('cross_type')
    color = request.form.get('color')

    # Открываем изображение
    img = Image.open(file.stream)

    # Сохраняем исходное изображение в память
    original_io = io.BytesIO()
    img.save(original_io, 'PNG')
    original_io.seek(0)
    original_b64 = base64.b64encode(original_io.read()).decode('utf-8')
    original_hist = get_color_histogram(img)

    # Рисуем крест
    draw = ImageDraw.Draw(img)
    width, height = img.size

    if cross_type == 'vertical':
        draw.line((width // 2, 0, width // 2, height), fill=color, width=5)
        draw.line((width // 3, height // 2, width // 1.5, height // 2), fill=color, width=5)
    else:
        # Горизонтальная линия по центру
        draw.line((0, height // 2, width, height // 2), fill=color, width=5)
        draw.line((width // 2, height // 3, width / 2, height // 1.5), fill=color, width=5)

    processed_hist = get_color_histogram(img)

    # Сохраняем обработанное изображение в память
    processed_io = io.BytesIO()
    img.save(processed_io, 'PNG')
    processed_io.seek(0)
    processed_b64 = base64.b64encode(processed_io.read()).decode('utf-8')

    # Возвращаем данные в формате JSON
    return jsonify({
        'original_image': 'data:image/png;base64,' + original_b64,
        'processed_image': 'data:image/png;base64,' + processed_b64,
        'original_hist': original_hist,
        'processed_hist': processed_hist
    })"""

if __name__ == '__main__':
    app.run(debug=True)