FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY src ./src
COPY sql ./sql
COPY app ./app
COPY data/raw ./data/raw
RUN mkdir -p data/processed reports/figures

# default: run the pipeline; the dashboard service overrides the command
CMD ["python", "-m", "src.pipeline"]
