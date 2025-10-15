FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY reformulate_moduledescription.py /app/

RUN pip install --no-cache-dir "openai>=1.55.0"

ENTRYPOINT ["python", "reformulate_moduledescription.py"]
