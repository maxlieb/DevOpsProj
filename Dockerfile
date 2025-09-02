FROM python:3.11-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000
ENV JOKE_LIMIT=20
# Optional envs you can override:
# ENV NTFY_BASE=https://ntfy.sh
# ENV NTFY_TOPIC=dadjokes-max-demo
# ENV NTFY_SINCE=72h
# ENV MAX_RECORDS=200
# ENV NTFY_AUTH=...

CMD ["python", "app.py"]
