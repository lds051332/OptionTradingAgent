FROM node:22-alpine AS frontend
WORKDIR /web
COPY web/package.json web/package-lock.json* ./
RUN npm install
COPY web/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml README.md ./
COPY option_desk ./option_desk
COPY --from=frontend /web/dist ./web/dist
RUN pip install --no-cache-dir -e .
ENV OPTION_DESK_WEB_HOST=0.0.0.0
ENV OPTION_DESK_WEB_PORT=8000
EXPOSE 8000
CMD ["python", "-m", "option_desk.web"]
