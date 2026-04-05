# Pastebin

A self-hosted cloud clipboard and pastebin service built with Flask and Redis. Designed for home lab use behind a Traefik reverse proxy.

## Features

- **Global scratchpad** — a shared, auto-syncing clipboard at `/` that persists across sessions
- **Shareable links** — generate a short URL for any snippet; links expire after a configurable duration
- **No login required** — intended for private/trusted network use

## Stack

- Python / Flask
- Redis (storage)
- Docker + Docker Compose
- Traefik (reverse proxy / TLS)

## Setup

```bash
docker compose up -d
```

The app will be available at `https://pastebin.<MY_DOMAIN>`.

## Configuration

All variables are set in `docker-compose.yml` under the relevant service's `environment` block.

### Web service

| Variable | Default | Description |
|---|---|---|
| `expiration_secs` | `86400` | Seconds before shared paste links expire; omit for no expiration |
| `max_paste_size` | `524288` | Max request body size in bytes; larger requests are rejected with HTTP 413 |
| `max_pastes_per_ip` | `24` | Max pastes a single IP can create per 24-hour window; excess requests are rejected with HTTP 429 |

### Redis service

| Variable | Default | Description |
|---|---|---|
| `REDIS_MAXMEMORY` | `256mb` | Total memory cap for Redis storage |
| `REDIS_MAXMEMORY_POLICY` | `allkeys-lru` | Eviction policy when the cap is hit; `allkeys-lru` drops least recently used pastes |

## Routes

| Route | Description |
|---|---|
| `GET /` | Load the global scratchpad |
| `POST /autosave` | Auto-save content to the global scratchpad |
| `POST /share` | Create a new shareable paste, returns `{ id }` |
| `GET /<paste_id>` | Load a paste by ID into the editor |
