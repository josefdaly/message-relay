# relay server

A simple asymmetric message relay. Each queue has a **sender ID** (sid) for pushing messages and a **recipient ID** (rid) for pulling them. The sid is shareable; the rid stays private.

## Running

**Production**
```bash
docker compose up -d --build
```

**Development**
```bash
docker compose up redis -d
REDIS_HOST=localhost flask --app app run --debug
```

## API

### `POST /queue`
Create a new queue. Returns a sid/rid pair.
```json
{ "sender_id": "...", "recipient_id": "..." }
```

### `POST /send/<sid>`
Push a message onto the queue.
```json
{ "message": "hello" }
```

### `GET /receive/<rid>`
Pop one message from the queue.
```json
{ "message": "hello" }
```

### `GET /receive/<rid>/drain`
Pop all pending messages at once.
```json
{ "messages": ["hello", "world"] }
```

### `GET /health`
Returns `{ "status": "ok" }` if Redis is reachable.
