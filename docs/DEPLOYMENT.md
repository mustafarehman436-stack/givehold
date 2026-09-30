# Deployment and publishing

## GitHub source repository

Publish this directory as the repository root, not the outer workspace. `.gitignore` excludes dependencies, build output, Python caches, and `.env`. Never upload `work/`, the portable PostgreSQL data, credentials, or a real donor export.

After authenticating the GitHub CLI with your own account, from this directory:

```sh
git init -b main
git config user.name "YOUR NAME"
git config user.email "YOUR VERIFIED OR GITHUB NOREPLY EMAIL"
git add .
git commit -m "Build GiveHold inventory and reservation prototype"
gh auth login
gh repo create givehold --public --source=. --remote=origin --push
```

Use your actual configured identity. A single honest initial commit is enough; don't fabricate backdated development history, adoption, or performance claims. The repository description can be: “Donation inventory prototype with PostgreSQL row locking, FastAPI, React, and concurrency tests.”

The included GitHub Actions workflow runs real PostgreSQL tests and builds the frontend. A green check is evidence from that run; don't claim it before it executes. Add a screenshot after running your own demo if helpful.

## Hosting later

Keep deployment provider-neutral: a Linux host capable of Docker Compose can run the current app; alternatively use a managed PostgreSQL instance and separate API/web containers. No provider account is required to understand or run the project locally. GitHub Pages alone cannot run this FastAPI/PostgreSQL backend.

Before exposing it beyond your own machine:

1. Add authentication and authorization to every mutation and relevant read. A volunteer ID in a request isn't proof of identity. For a private preview, gate the entire app and API behind an authenticated reverse proxy.
2. Replace local database credentials with secrets supplied at runtime. Use TLS for remote database connections, least-privilege roles, persistent storage, and verified backups/restores. Keep the database off public ports.
3. Build the images from this commit. Run `alembic upgrade head` once as a release step, before new API instances start. Do not run fictional seed automatically in a real environment.
4. Serve the frontend and `/api` under one HTTPS origin. Adjust nginx's upstream to the deployed API. Put a TLS reverse proxy in front; the current Compose HTTP bindings intentionally allow only localhost access.
5. Set request-size limits, rate limits, database connection limits, lock/statement timeouts, and operational logs without personal data. Decide how clients retry transient failures using the existing request key.
6. Run the PostgreSQL suite against a disposable `_test` database, then smoke-test reserve/cancel/fulfill against fictional staging data. Never point truncating test fixtures at application data.
7. For rollback, redeploy the previous compatible image. Back up before destructive migrations; don't blindly downgrade a live schema containing history.

Docker tags and direct dependencies are pinned for a repeatable starting point. Review security updates before deployment; this prototype does not assert that its pinned versions are production-hardened.

## Development without Docker

Use Python 3.12, Node 22+, and PostgreSQL 16. Create `shelterstock` and a separate `shelterstock_test` database. In `backend`, create a virtual environment, install `requirements.lock.txt`, set `DATABASE_URL` to a `postgresql+psycopg://` URL, run `alembic upgrade head`, then `python -m app.seed` and `uvicorn app.main:app --reload`. `requirements.txt` lists direct dependencies; `requirements.lock.txt` pins the full tested resolution used by Docker.

In `frontend`, run `npm ci` and `npm run dev`; Vite forwards `/api` to localhost:8000. `npm run build` checks TypeScript and emits production files. Windows sandbox environments may need `node node_modules/vite/bin/vite.js build --configLoader runner` to avoid restricted parent-directory traversal during config bundling.

For tests, set DATABASE_URL to the disposable `_test` database, migrate it, and run `pytest -q` from `backend`. The test suite truncates its application tables before each test; don't share that database with a running demo or another test worker.
