# JellyGulp

A self-hosted Jellyfin analytics and media-server dashboard.

## Included in this starter

- Live server status
- Library counts
- Jellyfin user count
- Active playback sessions
- Direct Play / Direct Stream / Transcode display
- PostgreSQL persistence
- Session polling every 10 seconds
- Basic historical playback-event recording
- React dark dashboard
- Docker Compose
- GitHub Actions builds to GHCR
- TrueNAS Custom App YAML template

## Local / server test

1. Copy `.env.example` to `.env`.
2. Fill in `JELLYFIN_API_KEY`.
3. Set `JELLYFIN_URL=http://192.168.1.246:30013`.
4. Run:

```bash
docker compose up -d --build
```

5. Open `http://SERVER-IP:30020`.

## GHCR deployment

Push this repository to GitHub. The included workflow builds:

- `ghcr.io/YOUR_GITHUB_USERNAME/jellygulp-backend:latest`
- `ghcr.io/YOUR_GITHUB_USERNAME/jellygulp-frontend:latest`

Then update the two image names in `truenas-app.yaml` and install it through the TrueNAS Custom App YAML screen.
