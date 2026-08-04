FROM tensorflow/tensorflow:2.15.0

WORKDIR /app

COPY . /app

RUN apt-get update && apt-get install -y libgl1 libglib2.0-0 && pip install --upgrade pip && pip install --no-cache-dir -r requirement.txt && python -c "import tensorflow as tf; print('TensorFlow version:', tf.__version__)"

EXPOSE 10000

CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:10000"]
