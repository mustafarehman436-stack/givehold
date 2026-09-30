# Verification record

Verified locally on September 24, 2026, using Python 3.12, a real PostgreSQL 16.8 server bound to localhost, and Node 24.19.0. Only fictional data was used.

| Check | Result |
|---|---|
| pytest application suite | 19 passed |
| Deterministic last-unit concurrency test | Passed; independent connection PIDs and observed PostgreSQL lock wait |
| Reservation insert failure rollback | Passed; stock counter and reservation both rolled back |
| Multi-item fulfillment failure rollback | Passed; all items and lifecycle states unchanged |
| Migration initial upgrade, downgrade to base, and re-upgrade | Passed on disposable test database |
| Alembic schema comparison | No new upgrade operations detected |
| TypeScript checking | Passed |
| Vite production build | Passed using `--configLoader runner` for the Windows sandbox |
| Live HTTP demo with independent sessions | One 200, one 409, exactly one reservation; counters consistent |
| Unsafe learning exercise | Reproduced two claims for one unit; removed its temporary tables afterward |
| Browser core workflow | Reserve, cancel, and collect passed against live API/PostgreSQL; history timestamp visible |

The test run emitted one dependency deprecation warning about Starlette's use of an AnyIO alias; it did not fail tests.

Docker was not installed in the build environment. The Dockerfiles and Compose workflow are provided, but their end-to-end container execution has not been verified here. The included CI workflow performs that check when the repository is pushed to GitHub. Native PostgreSQL validation is not a claim that Compose has run.

The cancellation exercise is deliberately unfinished and excluded from the normal test suite. Its separate checks are expected to fail until the learner implements it.

## Hosted demo follow-up — September 25, 2026

Deployed the public demo to Render's Free web service with Neon Free PostgreSQL 16. The hosted wrapper's tests bring the suite to 23 passing tests. GitHub Actions passed the PostgreSQL suite, Compose frontend build, and combined hosted Docker image build. The live HTTPS endpoint passed health, unauthorized-access rejection, authenticated frontend/API reads, reservation, and cancellation checks. The earlier Docker limitation above describes the original local build environment; CI subsequently verified the container builds.

Live URL: https://shelterstock-demo.onrender.com. The demo now opens publicly without credentials. The earlier access checks describe its initial deployment. No charity adoption or load benchmark is claimed.
