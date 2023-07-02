
FROM python:3.10 as requirements-stage

WORKDIR /tmp

RUN pip install poetry

COPY ./pyproject.toml ./poetry.lock* /tmp/


RUN poetry export -f requirements.txt --output requirements.txt --without-hashes

FROM python:3.10

WORKDIR /app

# Устанавливаем зависимости
RUN apt-get update \
    && apt-get install -y --no-install-recommends antiword

COPY --from=requirements-stage /tmp/requirements.txt /app/requirements.txt

RUN pip install --no-cache-dir --upgrade -r /app/requirements.txt

COPY . /app/

RUN groupadd -g 1601 aii_backend && \
    useradd -m -u 1601 -g aii_backend aii_backend

# Устанавливаем права доступа к папке с приложением
RUN chown -R aii_backend:aii_backend /app

## run collectstatic command
#RUN python manage.py collectstatic --noinput

# Запускаем приложение
USER aii_backend

# Heroku uses PORT, Azure App Services uses WEBSITES_PORT, Fly.io uses 8080 by default
CMD ["sh", "-c", "uvicorn server.main:app --host 0.0.0.0 --port 8082"]
