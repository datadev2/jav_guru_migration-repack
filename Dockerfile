FROM python:3.12.5-slim

RUN pip install poetry

RUN apt-get update -y && apt-get install -y --no-install-recommends \
    wget gnupg libgl1-mesa-glx && \
    wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /usr/share/keyrings/google-chrome.gpg && \
    echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list && \
    apt-get update -y && apt-get install -y google-chrome-stable && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
COPY poetry.lock .
RUN poetry config virtualenvs.create false && poetry install --no-interaction --no-ansi  --no-root

COPY . .
