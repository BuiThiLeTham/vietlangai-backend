FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml alembic.ini ./
COPY app ./app
COPY shared ./shared
COPY alembic ./alembic
RUN pip install --no-cache-dir .
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
