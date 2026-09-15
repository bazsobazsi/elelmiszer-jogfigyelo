FROM python:3.11-slim

WORKDIR /app

COPY . .

RUN pip install --no-cache-dir -r requirements.txt && \
    chmod +x healthcheck.sh

EXPOSE 8768

ENV PORT=8768
ENV ELELMISZER_DB_DIR=/data/db

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD ./healthcheck.sh

CMD ["python3", "serve.py"]