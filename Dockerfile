# Dev image: Python 3.11 fixed, editable install with test extras.
# Does not emulate SANE/USB or the Pi runtime (see issue #19).
FROM python:3.11-slim-bookworm

WORKDIR /workspace

RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        libc6-dev \
        libjpeg62-turbo-dev \
        zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# Install deps first for better layer caching when only tests/app change.
COPY pyproject.toml README.md ./
COPY app ./app

RUN pip install --upgrade pip \
    && pip install -e ".[dev]"

COPY conftest.py .coveragerc ./
COPY tests ./tests

CMD ["pytest", "-q"]
