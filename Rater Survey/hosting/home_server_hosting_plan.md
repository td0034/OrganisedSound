# Home Server Hosting Plan (Rater Survey)

## Goals
- Keep session creation private/offline.
- Serve only the rater session links on the public server.
- Prioritize this service even if other containers exist.
- Export ratings CSV regularly to a laptop for safety.

## Deployment model (recommended)
- Generate rater sessions locally (offline) on your laptop.
- Copy the session links into email/messages for raters.
- Host only the rater playback app on the server.

This avoids exposing the session-creation page publicly and keeps the rater label entry under your control.

## Server configuration
### 1) Ports and domain
- Run the web container behind a reverse proxy (Caddy/Traefik/Nginx).
- Serve at the root of a domain or subdomain (e.g., `https://raters.yourdomain.com`).
- Ensure the proxy forwards `Range` requests for video playback.
- Do not expose the Postgres port externally.

### 2) Volumes and persistence
Bind mount these paths so data survives restarts:
- `./clips_square` (read-only)
- `./exports`
- Postgres data (`pgdata` volume)

### 3) Secrets and access
- Set `TOKEN_SECRET` to a long random value.
- Set a strong `POSTGRES_PASSWORD`.
- Keep `/` (session creation page) off the public server:
  - Option A: run the app only on a private network/VPN
  - Option B: remove or protect the `/` route with basic auth at the proxy

### 4) Resource priority
- Give this service CPU/memory priority if needed.
- Add `restart: unless-stopped` to keep it resilient.
- Consider log rotation to avoid disk growth.

## Operational workflow
### A) Generate sessions locally
1) Run the app locally on your laptop.
2) Create sessions and copy links to raters.
3) Store a local list that maps `rater_label` -> `session link`.

### B) Host only the rater links
- On the server, keep the app running and respond to incoming session URLs.
- Ensure the domain is correct in the links you send.

### C) Add new clips
- Upload new clips into `clips_square` on the server.
- The app scan will pick up new files automatically within ~20 seconds.
- If you need to regenerate crops, do that locally and then sync the folder.

### D) Backups
- Regularly download `exports/ratings.csv` to your laptop.
- Optionally back up the Postgres volume for full audit/history.

## Suggested hardening (optional)
- Remove the `ports` mapping for the database in `docker-compose.yml`.
- Put the web service behind a reverse proxy with TLS.
- Add basic auth on `/` if the app is public, or only publish `/s/{token}` at the proxy.

## Checklist before going live
- [ ] Domain/subdomain set and TLS enabled.
- [ ] `/` not publicly accessible (or protected).
- [ ] `TOKEN_SECRET` and DB credentials updated.
- [ ] `clips_square` and `exports` volumes mounted.
- [ ] Test a session link end-to-end.
- [ ] Confirm `exports/ratings.csv` is updating.
