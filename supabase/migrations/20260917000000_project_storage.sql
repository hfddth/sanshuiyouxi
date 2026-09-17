-- 山水有戏：私有景区项目及其资料。仅登录者可访问自己的数据。
create table if not exists public.projects (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null default auth.uid() references auth.users(id) on delete cascade,
  title text not null,
  scenic_name text not null,
  payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists projects_owner_updated_idx on public.projects (owner_id, updated_at desc);
alter table public.projects enable row level security;
revoke all on table public.projects from anon, authenticated;
grant select, insert, update, delete on table public.projects to authenticated;

create policy "read own projects" on public.projects for select to authenticated
  using ((select auth.uid()) = owner_id);
create policy "create own projects" on public.projects for insert to authenticated
  with check ((select auth.uid()) = owner_id);
create policy "update own projects" on public.projects for update to authenticated
  using ((select auth.uid()) = owner_id)
  with check ((select auth.uid()) = owner_id);
create policy "delete own projects" on public.projects for delete to authenticated
  using ((select auth.uid()) = owner_id);

create or replace function public.touch_project_updated_at()
returns trigger language plpgsql set search_path = '' as $$
begin
  new.updated_at = now();
  return new;
end;
$$;
create trigger project_updated_at before update on public.projects
  for each row execute function public.touch_project_updated_at();

insert into storage.buckets (id, name, public, file_size_limit)
values ('project-assets', 'project-assets', false, 10485760)
on conflict (id) do nothing;

create policy "read own project files" on storage.objects for select to authenticated
  using (bucket_id = 'project-assets' and (storage.foldername(name))[1] = (select auth.uid())::text);
create policy "upload own project files" on storage.objects for insert to authenticated
  with check (bucket_id = 'project-assets' and (storage.foldername(name))[1] = (select auth.uid())::text);

