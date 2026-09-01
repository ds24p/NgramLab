# Server Requirements for NGRAM LAB

NGRAM LAB is a Shiny for Python application. For production or institutional hosting, the simplest setup is:

```text
HTTPS domain -> reverse proxy -> Docker container running NGRAM LAB
```

The container listens on port `8000`. The public domain should terminate HTTPS in a reverse proxy such as Caddy, Nginx, Traefik, or an institutional proxy.

## Server Requirements

- SSH access
- Administrator access with `sudo` or root privileges, if you are expected to install Docker, Docker Compose, or the reverse proxy yourself
- Permission to install and run Docker
- Permission to install Docker Compose or the Docker Compose plugin
- A virtual Linux server, preferably Ubuntu LTS
- 1 vCPU; 2 vCPUs recommended for multiple users
- 1 GB RAM; 2-4 GB recommended
- 20-100 GB storage, depending on logs, cache, and future datasets
- Public access to the application
- A domain such as:

```text
ngram.uni-konstanz.de
statspicker.uni-konstanz.de
tools.uni-konstanz.de/ngram
```

- HTTPS for the domain
- Reverse proxy, for example Nginx, Caddy, Traefik, or an institutional proxy
- Outbound HTTPS access, required for Google Ngram requests, downloading Python packages, and future integrations
- Automatic restart of Docker containers after reboot; this project uses `restart: unless-stopped`
- Firewall allowing ports `80` and `443`, with SSH restricted to administrators

For path-based hosting such as `tools.uni-konstanz.de/ngram`, confirm that the reverse proxy supports Shiny traffic correctly, including WebSocket or long-lived HTTP connections, and that the app is tested under the final path.

## Docker Deployment

Build and start the app with Docker Compose:

```bash
docker compose up -d --build
```

Check logs:

```bash
docker compose logs -f ngram-lab
```

Stop the app:

```bash
docker compose down
```

The included `compose.yaml` binds the container to `127.0.0.1:8000`, which is intended for use behind a reverse proxy. The reverse proxy should expose the app publicly over HTTPS.

Example reverse proxy configurations are included in:

- `deploy/Caddyfile.example`
- `deploy/nginx.conf.example`

Without Compose, run:

```bash
docker build -t ngram-lab .
docker run -d --name ngram-lab --restart unless-stopped -p 127.0.0.1:8000:8000 ngram-lab
```

## Keeping Disk Usage Small

The Docker build context is intentionally limited by `.dockerignore`. The image only receives:

- `app.py`
- `utils.py`
- `requirements.txt`
- `pages/*.py`
- `www/*`

Local development artifacts such as `.git`, `__pycache__`, `_site`, `_shinylive_app`, `shinylive-cache`, `rsconnect-python`, logs, and virtual environments are excluded from the Docker context.

The production image is based on `python:3.12-slim` and installs Python packages with `--no-cache-dir` and `--no-compile` to avoid pip caches and generated `.pyc` files. A final image size of roughly 500-550 MB is expected because the app depends on scientific Python libraries such as NumPy, Pandas, SciPy, Matplotlib, Plotly, and Shiny.

On the server, check Docker disk usage with:

```bash
docker system df
```

After rebuilding or updating the app, remove unused build cache:

```bash
docker builder prune -f
```

Remove old unused images:

```bash
docker image prune -f
```

Container logs are rotated in `compose.yaml` with a maximum of three 10 MB log files.
