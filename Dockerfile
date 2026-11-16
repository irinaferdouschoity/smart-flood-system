FROM python:3.12-slim
RUN useradd -m -u 1000 user
WORKDIR /app
RUN chown user:user /app
COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY --chown=user . .
USER user
ENV AUTO_SYNC_NASA=false
EXPOSE 7860
CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-7860}"]
