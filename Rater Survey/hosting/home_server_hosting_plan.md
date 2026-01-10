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
- Option A (recommended): run the web container behind a reverse proxy (Caddy/Traefik/Nginx).
- Serve at the root of a domain or subdomain (e.g., `https://raters.yourdomain.com`).
- Ensure the proxy forwards `Range` requests for video playback.
- Option B (HTTP-only domain): publish the app directly on `http://<domain>:18080` and forward port `18080` in your router.
- Do not expose the Postgres port externally.

### 2) Volumes and persistence
Bind mount these paths so data survives restarts:
- `./trimmed_clips` (read-only)
- `./exports`
- Postgres data (`pgdata` volume)

### 2a) Production compose file
- Use `docker-compose.prod.yml` on the server for safer defaults (no DB port exposure, restart policy, env-based secrets).
- Copy `Rater Survey/.env.example` to `Rater Survey/.env` and set `POSTGRES_PASSWORD` + `TOKEN_SECRET`.
- Run: `docker compose -f docker-compose.prod.yml up --build`

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
4) If generating links via script, use the live base URL:
   - `python Rater\\ Survey/hosting/generate_session_links.py --base-url http://55gpt.ddns.net:18080`

### B) Host only the rater links
- On the server, keep the app running and respond to incoming session URLs.
- Ensure the domain/port in the links you send matches the server (e.g., `http://55gpt.ddns.net:18080`).

### C) Add new clips
- Upload new clips into `trimmed_clips` on the server.
- The app scan will pick up new files automatically within ~20 seconds.
- If you need to regenerate trims or crops, do that locally and then sync the folder.

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
- [ ] `trimmed_clips` and `exports` volumes mounted.
- [ ] Test a session link end-to-end.
- [ ] Confirm `exports/ratings.csv` is updating.
