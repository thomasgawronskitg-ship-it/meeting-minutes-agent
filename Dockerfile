# ===============================
# Meeting Minutes Agent - Dockerfile
# Build CPU-only, compatibile Railway
# ===============================

FROM python:3.10-slim

# Env di base
ENV DEBIAN_FRONTEND=noninteractive \
    PIP_NO_CACHE_DIR=1 \
    HF_HUB_DISABLE_TELEMETRY=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Dipendenze di sistema
# - ffmpeg: richiesto da whisperx
# - libgomp1: richiesto da onnxruntime
RUN apt-get update && apt-get install -y \
    ffmpeg git curl gcc build-essential libgomp1 \
 && rm -rf /var/lib/apt/lists/*

# Utente non-root per il runtime
RUN useradd -m appuser
WORKDIR /app

# Toolchain Python aggiornato
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# PyTorch CPU (>=2.4 non usa più il suffisso +cpu)
# Usiamo l’index CPU ufficiale e pinniamo 2.8.0 (compatibile con whisperx==3.4.2)
RUN pip install --no-cache-dir --root-user-action=ignore \
    --index-url https://download.pytorch.org/whl/cpu \
    torch==2.8.0 torchaudio==2.8.0

# Dipendenze applicative
COPY requirements.txt .
# Fix difensivo nel caso compaia una riga errata "-numpy==..."
RUN sed -i 's/^\-numpy==\([0-9.]\+\)$/numpy>=2.0.2/' requirements.txt
RUN pip install --no-cache-dir -r requirements.txt && pip check

# Codice applicativo
COPY . .

# (Opzionale) Stampa versioni chiave a build-time per diagnosi
RUN python - << 'PY'
import importlib
mods = ['numpy','torch','torchaudio','whisperx','transformers']
for m in mods:
    try:
        print(f"{m}:", importlib.import_module(m).__version__)
    except Exception as e:
        print(f"{m}: <missing> ({e})")
PY

# Runtime
USER appuser
EXPOSE 8080
CMD ["gunicorn", "-b", "0.0.0.0:8080", "main:app"]
