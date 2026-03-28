# Stage 1: Build React frontend
FROM node:20-alpine AS frontend-build
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Python runtime
FROM python:3.12-slim
WORKDIR /app

COPY requirements.txt .
RUN apt-get update && apt-get install -y --no-install-recommends build-essential \
    && pip install --no-cache-dir -r requirements.txt \
    && apt-get purge -y build-essential && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*

COPY app/ ./app/

# Copy built frontend assets from stage 1
COPY --from=frontend-build /build/dist ./frontend/dist/

# Environment variables for runtime configuration
ENV S3_BUCKET_NAME=""
ENV AWS_REGION=""
ENV SESSION_SECRET=""
ENV DYNAMODB_TABLE_NAME=""

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
