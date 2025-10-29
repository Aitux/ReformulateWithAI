FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /workspace

RUN pip install --no-cache-dir uv

COPY pyproject.toml /tmp/project/pyproject.toml
COPY uv.lock /tmp/project/uv.lock

WORKDIR /tmp/project

RUN uv export --format requirements-txt --no-dev --locked --project /tmp/project > /tmp/project/requirements.txt
RUN uv pip install \
        --system \
        --break-system-packages \
        --no-cache \
        -r /tmp/project/requirements.txt

WORKDIR /workspace

COPY reformulator /workspace/reformulator

ENTRYPOINT ["python", "-m", "reformulator"]
