# ── Dockerfile for Views Bot ──────────────────
# Works on: Render, Railway, Fly.io, VPS

FROM python:3.11-slim

# Working directory
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt flask

# Copy all bot files
COPY . .

# Expose port for keep-alive server
EXPOSE 8080

# Run the bot
CMD ["python", "bot.py"]
