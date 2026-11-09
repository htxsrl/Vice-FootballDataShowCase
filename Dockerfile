FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# DEV=1 aggiunge le dipendenze di test (lo imposta docker-compose.yml); l'immagine pubblica resta senza.
ARG DEV=0
COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
 && if [ "$DEV" = "1" ]; then pip install --no-cache-dir -r requirements-dev.txt; fi

COPY vice ./vice
COPY data/processed ./data/processed
# il glossario dell'app: unica fonte la pagina della wiki (decisione 46, vice/glossario.py)
COPY wiki/metodi/glossario.md ./wiki/metodi/glossario.md

EXPOSE 8000

CMD ["uvicorn", "vice.main:app", "--host", "0.0.0.0", "--port", "8000"]
