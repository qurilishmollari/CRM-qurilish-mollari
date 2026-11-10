FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN python -m pip install --no-cache-dir -r requirements.txt && python -m gunicorn --version
COPY . .
RUN DJANGO_DEBUG=0 DJANGO_SECRET_KEY=build-only-static-assets DATABASE_URL=postgresql://build:build@localhost/build python manage.py collectstatic --noinput
RUN useradd --create-home crm
USER crm
CMD ["python", "-m", "config.start"]
