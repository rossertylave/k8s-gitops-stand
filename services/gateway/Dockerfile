FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .

# Непривілейований користувач: контейнер не працює від root
RUN useradd --system --uid 10001 app
USER 10001

ARG APP_VERSION=dev
ARG READY_FAIL=false
ENV APP_VERSION=${APP_VERSION} \
    READY_FAIL=${READY_FAIL}

EXPOSE 8080
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]
