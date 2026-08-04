FROM tensorflow/tensorflow:2.15.0

WORKDIR /app

COPY . /app

ENV PIP_BREAK_SYSTEM_PACKAGES=1

RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 && python -m pip install --upgrade pip && python -m pip install --no-cache-dir Flask==3.1.2 gunicorn==23.0.0 mysql-connector-python==9.4.0 PyMySQL==1.1.2 pillow==11.3.0 reportlab==4.2.0 matplotlib==3.8.4 opencv-python-headless==4.10.0.84 && python -c "import tensorflow as tf; print('TensorFlow version:', tf.__version__)"

EXPOSE 10000

CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:10000"]
