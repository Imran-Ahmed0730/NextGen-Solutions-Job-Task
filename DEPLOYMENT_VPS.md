# VPS Deployment Guideline

This guide describes the recommended path for deploying Sabuj Pran to an Ubuntu VPS. It covers
server preparation, DNS, secrets, database initialization, application startup, and ongoing
operations.

> **Production readiness warning:** The repository currently contains only a development Docker
> Compose configuration. It runs Next.js with `next dev`, starts Uvicorn with `--reload`, and
> publishes MySQL and API ports. The frontend Dockerfile does not currently provide a production
> build-time `NEXT_PUBLIC_API_URL` configuration. Do not expose the current Compose stack to the
> public internet or treat the commands in the local-development guide as production deployment.
> Before going live, the project needs a reviewed production Compose configuration and frontend
> image/build configuration. This guide describes the production requirements and deployment
> sequence; it does not claim those production artifacts already exist.

## 1. Recommended server architecture

Use an Ubuntu 24.04 LTS VPS with Docker Engine and the Docker Compose plugin:

```text
Internet
   |
   +-- HTTPS app.example.com --> Caddy reverse proxy --> Next.js production server
   |
   +-- HTTPS api.example.com --> Caddy reverse proxy --> FastAPI/Uvicorn
                                                    |
                                                    +--> MySQL (private Compose network)
```

Caddy can run on the host and provide automatic HTTPS certificates, or as a separately managed
container. Keep MySQL private to the Docker network. Publish only the reverse proxy's HTTP/HTTPS
ports to the internet. Use separate hostnames for the frontend and API because the frontend
currently calls the API using the `NEXT_PUBLIC_API_URL` setting.

## 2. Provision and secure the VPS

1. Create an Ubuntu 24.04 LTS VPS with enough disk space for the application, database, and backups.
   Assign a stable public IPv4 address; configure IPv6 only if it is also firewalled.
2. Create a non-root deployment account and use SSH keys. Disable direct root SSH login and
   password-based SSH authentication after confirming key-based access works.
3. Configure the provider firewall and the host firewall to allow:
   - SSH only from trusted administrator IPs where practical.
   - TCP 80 and 443 for HTTP-to-HTTPS redirection and HTTPS.
   - Do **not** allow public inbound access to ports 3000, 3306, or 8000.
4. Install Docker Engine and the Docker Compose plugin using Docker's official Ubuntu installation
   instructions. Grant Docker access only to trusted administrators; membership in the Docker group
   is effectively root access.
5. Apply Ubuntu security updates and configure regular unattended security updates.

## 3. Configure DNS and HTTPS

Create DNS records pointing to the VPS:

| Record | Type | Value |
| --- | --- | --- |
| `app.example.com` | A (and optional AAAA) | VPS public address |
| `api.example.com` | A (and optional AAAA) | VPS public address |

Replace `example.com` with the real domain. Wait for DNS to resolve before enabling automatic
certificate provisioning.

Configure Caddy with the following site routing, replacing both hostnames:

```caddy
app.example.com {
    reverse_proxy 127.0.0.1:3000
}

api.example.com {
    reverse_proxy 127.0.0.1:8000
}
```

Caddy obtains and renews TLS certificates when DNS points to the server and ports 80/443 are
reachable. If using a different reverse proxy, configure equivalent HTTPS termination and proxy
headers. Do not proxy to public-facing container ports.

## 4. Prepare the application configuration

1. Clone the repository into a deployment-owned directory, for example `/opt/sabuj-pran`, and
   select the release or commit that is to be deployed.
2. Create `.env` from `.env.example`; never commit it or copy development secrets into it.
3. Configure private, unique values for `SECRET_KEY`, `MYSQL_PASSWORD`, and
   `MYSQL_ROOT_PASSWORD`. Generate a signing key on the server or in a trusted secret manager:

   ```bash
   openssl rand -hex 48
   ```

   `SECRET_KEY` must be at least 32 characters and must not be a placeholder. Keep it stable:
   rotating it invalidates existing login sessions. Restrict `.env` file permissions to the
   deployment account (for example, `chmod 600 .env`).
4. Set the production frontend and API addresses:

   ```dotenv
   NEXT_PUBLIC_API_URL=https://api.example.com
   FRONTEND_ORIGIN=https://app.example.com
   ```

   `NEXT_PUBLIC_API_URL` must be supplied to the **frontend production build**, not just the
   running container, because Next.js embeds public environment variables into browser assets at
   build time. The current frontend Dockerfile/Compose setup does not yet implement that production
   build configuration.
5. Ensure `DATABASE_URL` uses the Compose-internal MySQL service name, database name, and the same
   credentials configured for the MySQL container. Do not use `localhost` for a database in another
   container. Do not publish the MySQL port.
6. Configure `SMTP_HOST`, `SMTP_FROM_EMAIL`, and SMTP credentials if password recovery is required.
   Set the company name, currency, timezone, and other business defaults before initializing
   company settings.
7. Use the production frontend origin exactly in `FRONTEND_ORIGIN`, including HTTPS. If the domain
   changes, update the API CORS setting and rebuild/restart the affected services.

## 5. Production configuration gate

Before starting public services, confirm a production Compose file/configuration has been reviewed
and committed. It must, at minimum:

- Run the frontend production build and `next start`, not `next dev`; pass
  `NEXT_PUBLIC_API_URL` at build time.
- Run Uvicorn without `--reload`, with production-appropriate worker/restart settings.
- Keep MySQL on an internal network with no public host port.
- Bind application ports to loopback only if Caddy runs on the host, or keep them private on a
  shared Docker network if Caddy is containerized.
- Preserve MySQL data, uploaded media, and other required state in durable volumes/bind mounts.
- Use restart policies, health checks, resource limits appropriate to the VPS, and pinned/reviewed
  image versions.
- Load secrets from protected server configuration rather than source control.

**This production configuration is not included in the repository's current Compose setup.**
Do not substitute the development `docker-compose.yml` for this gate. Once a production Compose
configuration has been implemented, use its documented file name and commands for the following
steps.

## 6. Initialize the database and administrator

Take a verified backup before running migrations against any existing database. On a fresh
installation:

1. Start the production database service and wait until its health check passes.
2. Build the production API image using the selected release and apply the schema:

   ```bash
   docker compose -f <production-compose-files> run --rm --no-deps api alembic upgrade head
   ```

   Replace `<production-compose-files>` with the actual production Compose file(s) once provided
   by the project. The current repository does not define this production command/configuration.
3. Create the initial administrator and company settings:

   ```bash
   docker compose -f <production-compose-files> run --rm --no-deps api \
     python -c "import app.main; from app.modules.auth.seed import main; main()"
   docker compose -f <production-compose-files> run --rm --no-deps api \
     python -m app.modules.company_settings.seed
   ```

   The first admin seed prints a randomly generated password only when it creates the account.
   Record and deliver that credential securely; do not put it in shell history, a ticket, or this
   document. Change it after the first sign-in and add a valid email address for recovery. Re-running
   the seed synchronizes permissions but does not reset an existing password.
4. Do not run `app.demo_seed` against production unless you intentionally want demo records.

## 7. Start and verify

After the production Compose configuration is available, start the production services using its
documented command, for example:

```bash
docker compose -f <production-compose-files> up --build -d
docker compose -f <production-compose-files> ps
```

Verify all of the following before handing over the service:

- `https://app.example.com/login` loads over HTTPS.
- `https://api.example.com/health` returns HTTP 200.
- Browser developer tools show successful API requests without CORS, mixed-content, or certificate
  errors.
- An administrator can sign in, access the dashboard, and change the initial password.
- Password reset works if SMTP has been configured.
- Restarting the application does not lose database records or uploaded company images.

Review logs without printing secret environment values:

```bash
docker compose -f <production-compose-files> logs --tail 100 api
docker compose -f <production-compose-files> logs --tail 100 web
docker compose -f <production-compose-files> logs --tail 100 db
```

## 8. Backups, updates, and recovery

- Back up MySQL using a database-aware backup procedure and back up the persistent company media
  directory. Encrypt backups, store copies outside the VPS, define retention, and test restoration.
- Before each release, review migrations and take a backup. Apply Alembic migrations before
  switching traffic to code that requires the new schema. Follow the project's migration
  compatibility requirements; do not edit an already-applied migration.
- Deploy a reviewed release/commit, build versioned images, apply migrations, and restart services
  using the production Compose configuration. Verify health and sign-in after every deployment.
- Keep a rollback plan that accounts for both the previous application image and database schema.
  Restoring an old image alone may not be safe after a non-backward-compatible migration.
- Monitor available disk space, service health, failed logins, and backup completion. Rotate
  credentials and signing keys through a controlled maintenance process.
- `docker compose down -v` can delete database volumes. Never use it as a routine restart or
  troubleshooting command on a server.

## 9. Current deployment status

The steps above are the VPS deployment plan, not proof that the application is currently ready for
production. The current repository needs the production Compose and frontend build configuration
described in Section 5 before there is a safe, copy-paste VPS deployment. Until then, use the
existing Compose configuration only for local development or a trusted, non-public test machine.
