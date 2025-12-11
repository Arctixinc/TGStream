# ---------------------------
# Base image: Python + ffmpeg
# ---------------------------
FROM python:3.10-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# ---------------------------
# Working directory
# ---------------------------
WORKDIR /app

# ---------------------------
# Copy project
# ---------------------------
COPY . /app

# ---------------------------
# Install dependencies
# ---------------------------
RUN pip install --no-cache-dir -r requirements.txt

# For clean logs
ENV PYTHONUNBUFFERED=1

# ---------------------------
# ENTRYPOINT: python -m TGLive
# ---------------------------
CMD ["python3", "-m", "TGLive"]
