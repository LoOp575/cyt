-- CYT Neuron Live Core: persistent, append-only prediction journal.
-- Apply in Supabase SQL Editor or via the project's migration workflow.
create table if not exists public.neuron_models (
  id text primary key,
  symbol text not null default 'BTCUSDT',
  version integer not null default 1,
  state jsonb not null,
  checksum text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.neuron_predictions (
  id uuid primary key default gen_random_uuid(),
  symbol text not null,
  candle_open_at timestamptz not null,
  created_at timestamptz not null default now(),
  target_at timestamptz not null,
  reference_price numeric not null,
  prediction_value numeric not null,
  direction text not null check (direction in ('UP','DOWN','FLAT')),
  probability_up numeric not null check (probability_up between 0 and 1),
  features jsonb not null,
  contributions jsonb not null,
  weights_snapshot jsonb not null,
  weights_version integer not null,
  model_version text not null,
  source text not null,
  feature_timeframe text not null default '5m',
  status text not null default 'pending' check (status in ('pending','labeled','invalid')),
  actual_price numeric,
  actual_return numeric,
  actual_direction text,
  is_correct boolean,
  brier_score numeric,
  labeled_at timestamptz,
  unique(symbol, candle_open_at)
);
create index if not exists neuron_predictions_created_idx on public.neuron_predictions (created_at desc);
create index if not exists neuron_predictions_pending_idx on public.neuron_predictions (status, target_at);

create table if not exists public.neuron_audits (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),
  symbol text not null default 'BTCUSDT',
  sample_count integer not null,
  metrics jsonb not null,
  feature_diagnostics jsonb not null default '{}'::jsonb,
  model_version integer not null
);
create index if not exists neuron_audits_created_idx on public.neuron_audits (created_at desc);

alter table public.neuron_models enable row level security;
alter table public.neuron_predictions enable row level security;
alter table public.neuron_audits enable row level security;

-- No anon/authenticated access. Backend uses the service-role key only.
revoke all on public.neuron_models from anon, authenticated;
revoke all on public.neuron_predictions from anon, authenticated;
revoke all on public.neuron_audits from anon, authenticated;
grant all on public.neuron_models to service_role;
grant all on public.neuron_predictions to service_role;
grant all on public.neuron_audits to service_role;
