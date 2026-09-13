-- Opportunity Engine — shared runtime store (Supabase / Postgres).
-- Run once in the Supabase SQL editor. Safe to re-run (IF NOT EXISTS).
-- Access is server-side only (service-role key). The frontend never touches Supabase.

-- Universe row-collections (markets/submarkets/audiences/problems/opportunities/
-- opportunity_scores/opportunity_rankings/problem_sources) + singleton _doc rows.
create table if not exists documents (
  collection  text not null,
  id          text not null,
  parent_id   text,
  data        jsonb not null,
  updated_at  timestamptz not null default now(),
  primary key (collection, id)
);
create index if not exists documents_collection_idx on documents (collection);
create index if not exists documents_parent_idx     on documents (parent_id);

-- Per-node dynamic-expansion cache metadata (status + provenance).
create table if not exists expansion_state (
  node_id     text primary key,
  status      text,
  data        jsonb not null,
  updated_at  timestamptz not null default now()
);

-- Atomic exploration claim (two-operator concurrency): PK insert-on-conflict.
create table if not exists exploration_claims (
  node_id     text primary key,
  operator    text not null,
  claimed_at  timestamptz not null default now()
);

-- Phase-8/9 dossier files: research/<opp_id>/<name>.json  ->  one row each.
create table if not exists dossier_files (
  opp_id      text not null,
  name        text not null,
  data        jsonb not null,
  updated_at  timestamptz not null default now(),
  primary key (opp_id, name)
);

-- Operator-attributed usage (no secrets).
create table if not exists usage_events (
  id          bigserial primary key,
  operator    text,
  provider    text,
  operation   text,
  node_id     text,
  queries     int default 0,
  results     int default 0,
  sources     int default 0,
  created_at  timestamptz not null default now()
);

-- Server-side sessions (opaque tokens).
create table if not exists sessions (
  token       text primary key,
  operator    text not null,
  expires_at  double precision not null
);

-- Lock down direct API access: enable RLS with NO policies, so the anon/public
-- key can do nothing. The server uses the service-role key, which bypasses RLS.
alter table documents          enable row level security;
alter table expansion_state    enable row level security;
alter table exploration_claims enable row level security;
alter table dossier_files       enable row level security;
alter table usage_events        enable row level security;
alter table sessions            enable row level security;
