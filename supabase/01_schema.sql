create extension if not exists vector;

create table if not exists public.meetings (
  id bigserial primary key,
  title text,
  date date,
  participants text[],
  summary text,
  decisions text[],
  actions jsonb,
  next_steps text[],
  transcript_text text,
  summary_embedding vector(384)
);

create table if not exists public.transcript_chunks (
  id bigserial primary key,
  meeting_id bigint references public.meetings(id) on delete cascade,
  chunk_text text,
  embedding vector(384)
);
create index if not exists transcript_chunks_embedding_idx on public.transcript_chunks using ivfflat (embedding vector_cosine_ops) with (lists = 100);

create or replace function public.match_transcript_chunks(
  query_embedding vector(384),
  match_count int default 5
) returns table (
  id bigint,
  meeting_id bigint,
  chunk_text text,
  similarity float
)
language sql stable as $$
  select id, meeting_id, chunk_text,
         1 - (embedding <=> query_embedding) as similarity
  from public.transcript_chunks
  order by embedding <=> query_embedding
  limit match_count;
$$;

alter table public.meetings enable row level security;
alter table public.transcript_chunks enable row level security;

create policy "meetings_select" on public.meetings for select using (true);
create policy "meetings_insert" on public.meetings for insert with check (true);
create policy "chunks_select" on public.transcript_chunks for select using (true);
create policy "chunks_insert" on public.transcript_chunks for insert with check (true);
