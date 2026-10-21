-- Ngôn Sắc Việt schema for Supabase Postgres.
-- Run in the Supabase SQL editor, or apply with psql using the direct connection.
-- The Python API connects as the database owner and bypasses RLS.
-- The Flutter anon key may only read the public catalog.

create table if not exists users (
  id text primary key,
  email text not null unique,
  password_hash text not null,
  display_name text not null,
  role text not null default 'member',
  created_at timestamptz not null
);

create table if not exists refresh_tokens (
  id text primary key,
  user_id text not null references users(id) on delete cascade,
  token_hash text not null unique,
  expires_at timestamptz not null,
  revoked_at timestamptz
);

create table if not exists languages (
  code text primary key,
  iso639_3 text not null,
  name_vi text not null,
  name_en text not null,
  script text not null,
  family text not null,
  role text not null,
  evaluation_tier integer not null,
  orthography text not null
);

create table if not exists ethnic_groups (
  id text primary key,
  slug text not null unique,
  name_vi text not null,
  name_en text not null,
  family text not null,
  region_vi text not null,
  region_en text not null,
  origin_vi text not null,
  origin_en text not null,
  language_code text not null references languages(code)
);

create table if not exists heritage_items (
  id text primary key,
  group_id text not null references ethnic_groups(id) on delete cascade,
  kind text not null,
  title_vi text not null,
  title_en text not null,
  body_vi text not null,
  body_en text not null,
  media_url text,
  unique (group_id, title_vi)
);

create table if not exists lessons (
  id text primary key,
  language_code text not null references languages(code),
  title_vi text not null,
  title_en text not null,
  summary_vi text not null,
  summary_en text not null,
  level text not null default 'basic'
);

create table if not exists phrases (
  id text primary key,
  lesson_id text not null references lessons(id) on delete cascade,
  native_text text not null,
  vi_text text not null,
  en_text text not null,
  verified boolean not null default false,
  source text
);

create table if not exists quiz_questions (
  id text primary key,
  lesson_id text not null references lessons(id) on delete cascade,
  prompt_vi text not null,
  prompt_en text not null,
  explanation_vi text not null,
  explanation_en text not null
);

create table if not exists quiz_choices (
  id text primary key,
  question_id text not null references quiz_questions(id) on delete cascade,
  text_vi text not null,
  text_en text not null,
  is_correct boolean not null default false
);

create table if not exists translation_logs (
  id text primary key,
  user_id text references users(id),
  mode text not null,
  source_lang text not null,
  target_lang text not null,
  source_text text not null,
  output_text text not null,
  route text not null,
  engine text not null,
  created_at timestamptz not null
);

create table if not exists contributions (
  id text primary key,
  client_id text not null unique,
  user_id text not null references users(id),
  language_code text not null references languages(code),
  source_lang text not null,
  target_lang text not null,
  source_text text not null,
  target_text text not null,
  note text,
  status text not null default 'pending',
  reviewer_id text references users(id),
  review_note text,
  created_at timestamptz not null,
  updated_at timestamptz not null
);

alter table languages enable row level security;
alter table ethnic_groups enable row level security;
alter table heritage_items enable row level security;
alter table lessons enable row level security;
alter table phrases enable row level security;
alter table quiz_questions enable row level security;
alter table quiz_choices enable row level security;
alter table contributions enable row level security;

create policy "public read languages" on languages for select using (true);
create policy "public read ethnic_groups" on ethnic_groups for select using (true);
create policy "public read heritage" on heritage_items for select using (true);
create policy "public read lessons" on lessons for select using (true);
create policy "public read verified phrases" on phrases for select using (verified = true);
create policy "public read questions" on quiz_questions for select using (true);

create or replace view quiz_choices_public as
  select id, question_id, text_vi, text_en from quiz_choices;

-- Answer keys stay on quiz_choices, which has no anon policy.
-- contributions have no anon policy. Devices push through the Python API.

grant select on languages, ethnic_groups, heritage_items, lessons, phrases, quiz_questions to anon, authenticated;
grant select on quiz_choices_public to anon, authenticated;
