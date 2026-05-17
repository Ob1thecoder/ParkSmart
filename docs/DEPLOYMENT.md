# ParkSmart Deployment Guide

This document covers deploying and maintaining ParkSmart in production.

## Architecture Overview

```
┌─────────────────────┐     ┌─────────────────────┐
│   Cloudflare Pages  │     │       Fly.io        │
│     (Frontend)      │────▶│      (Backend)      │
│                     │     │                     │
│  - React + Vite     │     │  - FastAPI          │
│  - Static files     │     │  - SQLite (volume)  │
│  - Global CDN       │     │  - ML Models        │
└─────────────────────┘     └─────────────────────┘
```

| Component | Platform | Cost | URL |
|-----------|----------|------|-----|
| Frontend | Cloudflare Pages | Free | `parksmart.pages.dev` |
| Backend | Fly.io | Free | `parksmart-api.fly.dev` |
| Database | SQLite on Fly.io volume | Free | N/A |

---

## Initial Deployment

### Backend (Fly.io)

1. **Install Fly CLI**
   ```bash
   curl -L https://fly.io/install.sh | sh
   ```

2. **Login**
   ```bash
   fly auth login
   ```

3. **Create app** (from project root)
   ```bash
   cd /path/to/ParkSmart
   fly launch --name parksmart-api --region syd --no-deploy
   ```

4. **Create persistent volume** (for SQLite)
   ```bash
   fly volumes create parksmart_data --region syd --size 1
   ```

5. **Set secrets**
   ```bash
   fly secrets set TFNSW_API_KEY=your_key OPENAI_API_KEY=your_key
   ```

6. **Deploy**
   ```bash
   fly deploy
   ```

7. **Verify**
   ```bash
   fly status
   curl https://parksmart-api.fly.dev/health
   ```

### Frontend (Cloudflare Pages)

1. Go to [pages.cloudflare.com](https://pages.cloudflare.com)
2. Connect GitHub repository
3. Configure build settings:

   | Setting | Value |
   |---------|-------|
   | Framework preset | Vite |
   | Build command | `npm run build` |
   | Build output | `dist` |
   | Root directory | `frontend` |

4. Add environment variable:
   - `VITE_API_URL` = `https://parksmart-api.fly.dev`

5. Deploy

---

## Updating the Application

### Backend Updates

```bash
cd /path/to/ParkSmart

# Make your changes, then:
fly deploy
```

**Zero-downtime deployment**: Fly.io performs rolling deployments by default.

### Frontend Updates

Frontend auto-deploys when you push to the connected branch (usually `main`).

```bash
git add .
git commit -m "Update frontend"
git push origin main
```

Cloudflare Pages will automatically build and deploy.

### Updating Environment Variables

**Backend (Fly.io):**
```bash
# View current secrets
fly secrets list

# Update a secret
fly secrets set OPENAI_API_KEY=new_key

# Remove a secret
fly secrets unset OLD_SECRET
```

**Frontend (Cloudflare Pages):**
1. Go to Cloudflare Dashboard → Pages → parksmart
2. Settings → Environment variables
3. Edit and save
4. Trigger a new deployment

---

## Database Management

### Accessing SQLite Database

```bash
# SSH into the Fly.io machine
fly ssh console

# Inside the machine
sqlite3 /data/parksmart.db

# Useful commands
.tables
SELECT COUNT(*) FROM car_parks;
SELECT COUNT(*) FROM occupancy_history;
.quit
```

### Database Backup

```bash
# Download database locally
fly ssh sftp get /data/parksmart.db ./backup.db
```

### Database Restore

```bash
# Upload database
fly ssh sftp shell
put local_backup.db /data/parksmart.db
```

---

## Monitoring & Logs

### View Logs

```bash
# Live logs
fly logs

# Recent logs
fly logs --no-tail
```

### Check App Status

```bash
fly status
```

### Check Volume Usage

```bash
fly volumes list
```

---

## Scaling

### Increase Memory/CPU

Edit `fly.toml`:
```toml
[[vm]]
  memory = '2gb'  # Increase from 1gb
  cpu_kind = 'shared'
  cpus = 2        # Increase from 1
```

Then redeploy:
```bash
fly deploy
```

### Add More Regions

```bash
fly scale count 2 --region syd,mel
```

---

## Troubleshooting

### Backend Not Starting

```bash
# Check logs
fly logs

# SSH in and check manually
fly ssh console
```

### Database Issues

```bash
# Check if volume is mounted
fly ssh console
ls -la /data/

# Check database integrity
sqlite3 /data/parksmart.db "PRAGMA integrity_check;"
```

### Frontend Not Connecting to Backend

1. Verify `VITE_API_URL` is set correctly in Cloudflare Pages
2. Check CORS settings in backend (`app/main.py`)
3. Test backend health: `curl https://parksmart-api.fly.dev/health`

---

## Rolling Back

### Backend Rollback

```bash
# List recent deployments
fly releases

# Rollback to previous version
fly deploy --image registry.fly.io/parksmart-api:v123
```

### Frontend Rollback

1. Go to Cloudflare Dashboard → Pages → parksmart
2. Deployments tab
3. Click on a previous deployment
4. "Rollback to this deployment"

---

## Cost Summary

| Resource | Free Tier Limit |
|----------|-----------------|
| Fly.io VMs | 3 shared-cpu VMs |
| Fly.io Volume | 3GB total |
| Fly.io Bandwidth | 160GB/month outbound |
| Cloudflare Pages | Unlimited |
| Cloudflare Bandwidth | Unlimited |

**Estimated monthly cost: $0** (within free tier limits)
