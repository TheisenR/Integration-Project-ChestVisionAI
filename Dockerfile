FROM tensorflow/tensorflow:2.15.0

WORKDIR /app

COPY . /app

ENV PIP_BREAK_SYSTEM_PACKAGES=1

RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 && python -m pip install --upgrade pip && python -m pip install --no-cache-dir -r requirement.txt && python -c "import tensorflow as tf; print('TensorFlow version:', tf.__version__)"

EXPOSE 10000

CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:10000"]
