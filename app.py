from flask import Flask, render_template, request, session, jsonify
from flask_wtf import FlaskForm
from wtforms import FileField, RadioField, StringField, SubmitField
from wtforms.validators import DataRequired
import io
import os
import base64
import requests
import random
import string
import numpy as np
from PIL import Image, ImageDraw

#from captcha.image import ImageCaptcha

# Тест для CI/CD
app = Flask(__name__, template_folder=os.path.join(os.path.dirname(__file__), 'templates'))
app.config['SECRET_KEY'] = '12345'
#app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['RECAPTCHA_PUBLIC_KEY'] = '6LfrkY0sAAAAALVCa27xBLHxQ8qzSzoSFdNwG3od'
app.config['RECAPTCHA_PRIVATE_KEY'] = '6LfrkY0sAAAAAC8s61zINrelmAoGkZon1Aof3LKY'

class ImageForm(FlaskForm):
    """Форма для обработки изображения"""
    image = FileField('Изображение', validators=[DataRequired()])
    cross_type = RadioField('Тип креста',
                           choices=[('vertical', 'Вертикальный'),
                                   ('horizontal', 'Горизонтальный')],
                           default='vertical')
    color = StringField('Цвет', default='#ff0000')


def verify_recaptcha(response_token):
    """Проверяет токен reCAPTCHA"""
    secret_key = app.config['RECAPTCHA_PRIVATE_KEY']
    verify_url = 'https://www.google.com/recaptcha/api/siteverify'

    data = {
        'secret': secret_key,
        'response': response_token
    }

    result = requests.post(verify_url, data=data)
    response_json = result.json()

    return response_json.get('success', False)

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

    form = ImageForm()

    return render_template('index.html',
                          form=form,
                          recaptcha_public_key=app.config['RECAPTCHA_PUBLIC_KEY'])

@app.route('/process', methods=['POST'])
def process():
    from PIL import Image, ImageDraw

    recaptcha_response = request.form.get('g-recaptcha-response')

    if not recaptcha_response:
        return jsonify({'error': 'Подтвердите, что вы не робот!'}), 400

    if not verify_recaptcha(recaptcha_response):
        return jsonify({'error': 'Неверная капча! Попробуйте ещё раз.'}), 400

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

    original_hist = get_color_histogram(img)

    draw = ImageDraw.Draw(img)
    width, height = img.size

    if cross_type == 'vertical':
        draw.line((width // 2, 0, width // 2, height), fill=color, width=5)
        draw.line((width // 3, height // 2, width // 1.5, height // 2), fill=color, width=5)
    else:
        draw.line((0, height // 2, width, height // 2), fill=color, width=5)
        draw.line((width // 2, height // 3, width // 2, height // 1.5), fill=color, width=5)

    processed_hist = get_color_histogram(img)

    processed_io = io.BytesIO()
    img.save(processed_io, 'PNG')
    processed_io.seek(0)
    processed_b64 = base64.b64encode(processed_io.read()).decode('utf-8')


    return jsonify({
        'original_image': 'data:image/png;base64,' + original_b64,
        'processed_image': 'data:image/png;base64,' + processed_b64,
        'original_hist': original_hist,
        'processed_hist': processed_hist
    })

if __name__ == '__main__':
    app.run(debug=True)