FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir \
    fastapi "uvicorn[standard]" sqlalchemy "bcrypt>=4.1" pyjwt "pydantic[email]"

COPY pidge_server ./pidge_server

ENV PIDGE_DATA_DIR=/data
VOLUME ["/data"]

EXPOSE 8000
CMD ["uvicorn", "pidge_server.main:app", "--host", "0.0.0.0", "--port", "8000"]
