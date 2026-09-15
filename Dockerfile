FROM python:3.11-slim

WORKDIR /app

# Teljes projekt másolása
COPY . /app/

RUN pip install --no-cache-dir -r requirements.txt && \
    mkdir -p /data/db /data/pdfs && \
    ELELMISZER_DB_DIR=/data/db python3 db.py

EXPOSE 8768

ENV ELELMISZER_DB_DIR=/data/db
ENV ELELMISZER_PDF_DIR=/data/pdfs
ENV PORT=8768

CMD ["python3", "serve.py"]