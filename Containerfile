FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml .
COPY str_assistant/ ./str_assistant/

RUN pip install --no-cache-dir .

EXPOSE 8081

CMD ["str-assistant"]
