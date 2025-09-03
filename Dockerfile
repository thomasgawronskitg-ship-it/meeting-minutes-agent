FROM python:3.10-slim
ENV DEBIAN_FRONTEND=noninteractive PIP_NO_CACHE_DIR=1 HF_HUB_DISABLE_TELEMETRY=1 PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y ffmpeg git curl gcc build-essential libgomp1 && rm -rf /var/lib/apt/lists/*
RUN useradd -m appuser
WORKDIR /app
RUN pip install --no-cache-dir --upgrade pip setuptools wheel
RUN pip install --no-cache-dir --root-user-action=ignore torch==2.8.0+cpu torchaudio==2.8.0+cpu -f https://download.pytorch.org/whl/cpu/torch_stable.html
COPY requirements.txt .
RUN sed -i 's/^\-numpy==\([0-9.]\+\)$/numpy>=2.0.2/' requirements.txt
RUN pip install -r requirements.txt && pip check
COPY . .
RUN python -c "import importlib;mods=['numpy','torch','torchaudio','whisperx','transformers']; [print(m+':', importlib.import_module(m).__version__) for m in mods]"
USER appuser
EXPOSE 8080
CMD ["gunicorn", "-b", "0.0.0.0:8080", "main:app"]
