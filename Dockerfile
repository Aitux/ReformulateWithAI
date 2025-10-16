FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /workspace

RUN pip install --no-cache-dir uv

COPY reformulator/pyproject.toml /tmp/project/pyproject.toml
COPY reformulator/uv.lock /tmp/project/uv.lock
RUN uv export --format requirements-txt --no-dev --locked --project /tmp/project > /tmp/project/requirements.txt
RUN uv pip install \
        --system \
        --break-system-packages \
        --no-cache \
        -r /tmp/project/requirements.txt
        

COPY reformulator/reformulate_moduledescription.py /workspace/reformulator/

ENTRYPOINT ["python", "reformulator/reformulate_moduledescription.py"]
