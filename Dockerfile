FROM python:3.11-slim

WORKDIR /app

# Másold a teljes projektet
COPY . .

# Telepítsd a függőségeket
RUN pip install --no-cache-dir -r requirements.txt

# Inicializáld az adatbázist
RUN mkdir -p /data/db /data/pdfs && \
    ELELMISZER_DB_DIR=/data/db python3 db.py

EXPOSE 8768

ENV PORT=8768
ENV ELELMISZER_DB_DIR=/data/db

CMD ["python3", "serve.py"]