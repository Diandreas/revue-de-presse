FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Dépendances système :
# - libpq-dev / gcc : compilation psycopg
# - poppler-utils : pdf2image (rendu des pages des PDF scannés en images, quel que soit le moteur d'OCR)
# - tesseract-ocr(-fra) : moteur d'OCR LOCAL, utilisé seulement si OCR_ENGINE=tesseract (ou `auto` sans clé
#   Mistral). Avec une clé Mistral, les photos sont lues par le modèle de vision : ces 2 paquets sont alors
#   facultatifs (on les garde : repli hors ligne, coût ~40 Mo).
# - libpango/libcairo/libgdk-pixbuf : WeasyPrint (export PDF)
# - postgresql-client : pg_isready utilisé par entrypoint.sh
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    postgresql-client \
    poppler-utils \
    tesseract-ocr \
    tesseract-ocr-fra \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf2.0-0 \
    libcairo2 \
    libffi-dev \
    shared-mime-info \
    && rm -rf /var/lib/apt/lists/*

ARG REQUIREMENTS_FILE=requirements/dev.txt
COPY requirements/ requirements/
RUN pip install -r ${REQUIREMENTS_FILE}

COPY . .

RUN chmod +x entrypoint.sh

ENTRYPOINT ["./entrypoint.sh"]
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
