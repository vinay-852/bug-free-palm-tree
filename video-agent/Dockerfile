FROM python:3.11-slim

# --- system deps: node, ffmpeg, Chrome runtime libs, Indic + emoji fonts ---
RUN apt-get update && apt-get install -y --no-install-recommends \
      curl ca-certificates gnupg ffmpeg \
      libnss3 libnspr4 libatk1.0-0t64 libatk-bridge2.0-0t64 libcups2t64 \
      libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 \
      libgbm1 libasound2t64 libpango-1.0-0 libcairo2 \
      fonts-liberation fonts-noto-core fonts-noto-extra fonts-noto-color-emoji \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# --- python deps ---
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --- node deps + pre-download Chrome Headless Shell (baked into the image) ---
COPY remotion/package.json remotion/package-lock.json remotion/
RUN cd remotion && npm ci --no-audit --no-fund && npx remotion browser ensure

# --- app ---
COPY . .
# Docker COPY drops empty dirs; the pipeline writes into these at runtime.
RUN mkdir -p /app/remotion/public /app/remotion/out /app/out /app/.tmp \
    && useradd -m app && chown -R app:app /app
USER app

EXPOSE 8000
CMD ["uvicorn", "web:app", "--host", "0.0.0.0", "--port", "8000"]