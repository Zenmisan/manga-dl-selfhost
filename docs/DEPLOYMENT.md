# Deployment Guide (Free Tier)

This guide explains how to deploy **manga-dl** for free using a combination of cloud providers.

## Architecture
- **Frontend**: [Firebase Hosting](https://firebase.google.com/) (Free CDN)
- **Backend**: [Render](https://render.com/) (Free Web Service using Docker)
- **Database**: [Supabase](https://supabase.com/) (Free PostgreSQL)

---

## 1. Database Setup (Supabase)
Free hosting providers like Render use ephemeral storage, meaning SQLite files are deleted on every restart. You **must** use an external database for persistence.

1. Create a free project at [Supabase](https://supabase.com/).
2. Navigate to **Project Settings > Database**.
3. Copy the **Connection String (URI)**.
4. Modify the prefix from `postgresql://` to `postgresql+asyncpg://` (this is required for the async backend).
   - *Example:* `postgresql+asyncpg://postgres:password@db.xxxx.supabase.co:5432/postgres`

---

## 2. Backend Deployment (Render)
Render allows you to deploy the backend using the provided `Dockerfile`.

1. Push your project to a GitHub repository.
2. Sign in to [Render](https://render.com/) and create a new **Web Service**.
3. Connect your GitHub repository.
4. Set the following:
   - **Runtime**: `Docker`
   - **Instance Type**: `Free`
5. Add these **Environment Variables**:
   - `DATABASE_URL`: Your Supabase URI. 
     - *Note:* The app automatically converts `postgres://` to the required `postgresql+psycopg://` format for you.
   - `API_KEY`: A secure secret of your choice.
   - `CORS_ORIGINS`: `https://your-firebase-app.web.app`
     - *Note:* You can provide a single URL, a comma-separated list, or a JSON array.
   - `SUPABASE_URL`: Your Supabase Project URL (e.g. `https://xxxx.supabase.co`).
   - `SUPABASE_SERVICE_KEY`: Your Supabase **Service Role** Key (needed for bucket uploads/deletions).
   - `MAX_STORAGE_MB`: (Optional) Limit in MB before old unpinned chapters are evicted. Default is 900.

   - `LIBRARY_PATH`: `/tmp/manga-library`
   - `CACHE_PATH`: `/tmp/manga-cache`

*Note: Render Free tier services sleep after 15 minutes of inactivity. The first request after a break may take ~60 seconds to wake up.*

---

## 3. Frontend Deployment (Firebase)

### Update API Configuration
Modify `frontend/src/lib/api.ts` to point to your new backend:

```typescript
const api = axios.create({
  baseURL: 'https://your-backend-name.onrender.com/api',
  headers: { 'Content-Type': 'application/json' },
})
```

### Build and Deploy
1. Install Firebase Tools: `npm install -g firebase-tools`
2. Login: `firebase login`
3. Initialize: `firebase init hosting` (Set public directory to `frontend/dist`)
4. Build:
   ```bash
   cd frontend
   npm run build # or bun run build
   ```
5. Deploy: `firebase deploy --only hosting`

### 5. Troubleshooting Common Issues

#### `OSError: [Errno 101] Network is unreachable`
This happens on Render Free Tier because it doesn't support IPv6 outbound. By default, Supabase's direct connection host (`db.xxxx.supabase.co`) resolves to IPv6.

**Solution**: Use the **Supabase Transaction Pooler** (IPv4) connection string.
1. In Supabase, go to **Settings > Database**.
2. Scroll to **Connection String**.
3. Select the **Transaction Pooler** tab.
4. Ensure the mode is set to **Transaction**.
5. Copy the URI (it usually uses port **6543** and a hostname starting with `aws-0-`).
6. Append `?sslmode=require` to the end of your `DATABASE_URL` on Render.

*Correct Format:* `postgresql+psycopg://postgres:pass@aws-0-us-east-1.pooler.supabase.com:6543/postgres?sslmode=require`
