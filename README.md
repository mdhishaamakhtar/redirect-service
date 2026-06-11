# Redirect Service

A minimal Flask service that issues a `301` redirect to the `redirect_uri` query parameter.

## What it does

- Accepts `GET /?redirect_uri=https://example.com`
- Validates that the target uses `http` or `https`
- Rejects missing, malformed, or overly long redirect targets with `400`

## Local run

Install dependencies:

```bash
pip install -r requirements.txt
```

Run the app:

```bash
python app.py
```

The service listens on `0.0.0.0:8080` by default. Set `PORT` to change it.

## Docker

Build and run with Docker Compose:

```bash
docker compose up --build
```

The container publishes port `8080` by default. Set `PUBLISH_PORT` to change the host port.

## Example

```bash
curl -i "http://localhost:8080/?redirect_uri=https://example.com"
```

