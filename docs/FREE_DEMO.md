# Free hosting: Render + Neon

The hosted demo uses the real FastAPI application and PostgreSQL transactions.
One Render web service serves both the compiled React frontend and `/api`.
Neon holds the database. Local Docker Compose still works as before.

## Accounts and cost

Use only Render's Free web-service plan and Neon's Free database plan. Do not
upgrade or add paid resources. Free usage limits can suspend service; they do
not make this a production hosting arrangement. Check current terms at
[Render](https://render.com/docs/free) and [Neon](https://neon.com/pricing).
Render's free app sleeps after 15 minutes of inactivity and can take about a
minute to wake. Allow for this delay when opening the application. Do not use
artificial keep-alive traffic. Render's free PostgreSQL expires after 30 days;
the instructions use Neon instead.

## Deploy

1. Create a Neon Free project for fictional GiveHold demo data. Copy its
   direct PostgreSQL connection URL privately. Keep TLS enabled. Change the
   URL prefix from `postgresql://` to `postgresql+psycopg://`; preserve the
   username, password, host, database, and SSL query parameters.
2. In Render, create a Blueprint from this GitHub repository using `render.yaml`,
   or create one Free Docker web service with the repository root Dockerfile.
3. Set `DATABASE_URL` to the Neon URL as a secret environment variable. Never
   put the database connection string in GitHub or a screenshot.
4. Deploy. Startup applies migrations and seeds fictional data only if absent.
   `/health` is the readiness route. Render supplies the port and HTTPS URL.
5. Visit the HTTPS URL directly; no account or password is required. Verify
   reserve, cancel, and fulfill, then share the public URL.

## Limits and operation

All visitors share the same fictional records. A cancelled reservation releases
stock; collected units stay collected. Add more fictional stock through Edit
before a later demonstration if necessary. Refresh to see another visitor's
updates. There is no destructive public reset endpoint.

`app/hosted.py` serves the public frontend and API and rejects cross-origin
browser writes. Anyone with the URL can edit the shared fictional records.
This public instance uses shared fictional data, without individual volunteer accounts or production
authorization. Use only fictional data. HTTPS is required.

Test the hosted wrapper with the normal PostgreSQL pytest suite.
