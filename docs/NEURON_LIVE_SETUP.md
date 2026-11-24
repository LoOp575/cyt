# CYT Neuron Live Core setup

## What this branch adds

- A redesigned Neuron screen with live neural topology, synapse weights, immutable prediction journal, and audit views.
- A five-minute Vercel Cron entry at `/api/neuron/cron`.
- Server-only Supabase PostgREST storage for model snapshots, predictions, matured outcomes, and audit reports.
- The cron worker predicts from the last fully closed BTCUSDT 5m candle and evaluates the next 5m candle close.
- Champion weights are not automatically changed. This branch only records and audits; candidate training/promotion remains a gated follow-up.

## Required environment variables

Set these in Vercel Project Settings → Environment Variables:

- `SUPABASE_URL`: URL of a dedicated active Supabase project.
- `SUPABASE_SERVICE_ROLE_KEY`: service-role secret. Server-side only, never prefix with `REACT_APP_`.
- `NEURON_CRON_SECRET`: long random secret. Vercel Cron sends `Authorization: Bearer <secret>` when configured as `CRON_SECRET`; this route accepts either `NEURON_CRON_SECRET` or `CRON_SECRET`.

## Database

Apply `supabase/migrations/202611240001_neuron_live_core.sql` to the dedicated CYT database. RLS is enabled and anon/authenticated roles have no table access. Only the backend service-role key can read/write these tables.

The currently connected Supabase account showed only inactive projects at implementation time. No existing project was reactivated or modified. Use a dedicated active project or explicitly choose an existing one before applying the migration.

## Important model caveat

The existing neuron weights were initialized around the original screening feature definitions. The 5m worker computes the existing screening-v2 feature transform on 5m candles, so this is an experimental timeframe adaptation. The output is explicitly provisional and `(tanh(y)+1)/2` is only a monotonic score mapping, not a calibrated probability. The Brier score is diagnostic, not proof of predictive edge. Collect an adequate out-of-sample sample before interpreting accuracy or enabling candidate promotion.

## Five-minute scheduler

The five-minute schedule uses GitHub Actions rather than Vercel Cron so the Vercel deployment does not depend on the account's Cron frequency tier. The workflow is `.github/workflows/neuron-live-cron.yml`.

Configure these GitHub repository settings:
- **Actions → Variables**: `CYT_API_BASE_URL` = the exact production base URL of this CYT deployment (no trailing slash).
- **Actions → Secrets**: `NEURON_CRON_SECRET` = the same random secret configured as the Vercel environment variable `NEURON_CRON_SECRET`.

GitHub scheduled workflows run from the repository's default branch. Merge this workflow to `main` before expecting automatic scheduled runs. `workflow_dispatch` is available for a manual test. GitHub schedule events use UTC and can be delayed under load; check the Actions run history and database timestamps. The UI countdown is only a clock display, not proof that the scheduler ran.
