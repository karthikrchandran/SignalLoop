FROM python:3.11-slim

WORKDIR /app
RUN pip install --no-cache-dir fastapi "uvicorn[standard]" python-multipart faster-whisper

COPY main.py .

ENV WHISPER_MODEL=base
ENV WHISPER_DEVICE=cpu
ENV WHISPER_COMPUTE_TYPE=int8

EXPOSE 9000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "9000"]
