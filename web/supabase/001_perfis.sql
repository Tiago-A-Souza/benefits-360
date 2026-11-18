-- Perfis do Benefits 360.
-- Rodar no SQL Editor do projeto Supabase (não executar pelo app).
-- Cada conta nova vira corretor. O front não altera o papel.

create table if not exists public.perfis (
  id uuid primary key references auth.users on delete cascade,
  email text,
  nome text,
  papel text not null default 'corretor' check (papel in ('corretor', 'admin')),
  criado_em timestamptz not null default now()
);

alter table public.perfis enable row level security;

revoke all on table public.perfis from anon, public;
grant select on table public.perfis to authenticated;

drop policy if exists ler_proprio_perfil on public.perfis;
create policy ler_proprio_perfil
  on public.perfis
  for select
  to authenticated
  using (auth.uid() = id);

-- Sem políticas de insert/update/delete: o front só lê o próprio perfil.
-- O papel não pode ser alterado pelo browser (nem por UPDATE).

create or replace function public.criar_perfil_novo_usuario()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.perfis (id, email, nome, papel)
  values (
    new.id,
    new.email,
    coalesce(new.raw_user_meta_data->>'nome', ''),
    'corretor'
  );
  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute procedure public.criar_perfil_novo_usuario();
