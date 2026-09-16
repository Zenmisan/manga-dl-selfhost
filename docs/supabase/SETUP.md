# Supabase Setup Guide

## Dashboard Configuration

### 1. Authentication — Redirect URLs

**Required before signup works on web.**

Location: Supabase Dashboard → Authentication → URL Configuration → Redirect URLs

Add:
```
https://manga-dl.web.app/login
```

Without this, the email confirmation link will be rejected as an unauthorized redirect.

Code reference: `frontend/src/pages/Register.tsx`
```ts
options: { emailRedirectTo: 'https://manga-dl.web.app/login' }
```

---

### 2. Storage Buckets

| Bucket | Access | Purpose |
|---|---|---|
| `manga-backups` | Private (per-user RLS) | CBZ cloud backup uploads |

Create via: Supabase Dashboard → Storage → New bucket → `manga-backups` → Private

---

### 3. SQL Migrations

Run all migrations in: `docs/supabase/migrations.sql`

Location: Supabase Dashboard → SQL Editor → paste and run

Tables created:
- `reading_progress` — chapter read tracking, synced from client
- `read_tracking` — reading session history
- `user_categories` — library category sync
- `manga_notes` — per-manga user notes
- `manga_overrides` — metadata overrides (title/cover/description)

All tables use RLS policies scoped to `auth.uid()`.

---

### 4. Environment Variables

These are baked into the frontend bundle at build time via Vite.

Required in `frontend/.env` (or set in Firebase / CI environment):
```
VITE_SUPABASE_URL=https://<project-ref>.supabase.co
VITE_SUPABASE_ANON_KEY=<anon-key>
```

Get these from: Supabase Dashboard → Project Settings → API

---

### 5. Auth Provider

Currently using **Email + Password** only.

To enable: Supabase Dashboard → Authentication → Providers → Email → Enable

Recommended settings:
- Confirm email: **On**
- Secure email change: **On**
- Double confirm email changes: **On**
