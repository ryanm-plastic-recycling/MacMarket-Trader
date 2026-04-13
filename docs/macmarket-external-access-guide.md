# MacMarket Trader — External Access Setup Guide
# Making the app accessible at https://macmarket.io

Last updated: April 2026
Assumes: App is currently running locally at localhost:9500 (frontend) and localhost:9510 (backend)

---

## Overview of what needs to happen

```
Internet → macmarket.io (your public IP) → Router port forward → 
Windows machine → Caddy (reverse proxy, handles HTTPS) → 
Next.js :9500 / FastAPI :9510
```

Clerk requires HTTPS for production. Caddy handles SSL automatically 
using Let's Encrypt — no manual certificate management needed.

---

## PART 1 — Prerequisites checklist

Before starting, confirm:

- [ ] You own the domain macmarket.io and can manage DNS
- [ ] Your Windows machine has a static local IP (set this first — see Step 1)
- [ ] You have admin access to your router
- [ ] Your ISP does not block inbound ports 80 and 443 (most residential ISPs allow this)
- [ ] Caddy is installed (see reverse proxy guide)

---

## PART 2 — Step by step

### Step 1 — Give your Windows machine a static local IP

Your router assigns your machine a local IP (like 192.168.1.x). 
By default this changes on reboot. Fix it:

1. Open **Settings → Network & Internet → Ethernet** (or WiFi)
2. Click your connection → **Edit** under IP assignment
3. Switch to **Manual**
4. Set:
   - IP address: `192.168.1.100` (pick something outside your router's DHCP range)
   - Subnet mask: `255.255.255.0`
   - Gateway: your router IP (usually `192.168.1.1`)
   - DNS: `8.8.8.8`
5. Save

Write down this IP — you'll need it for router port forwarding.

---

### Step 2 — Set up router port forwarding

1. Open your router admin panel (usually http://192.168.1.1)
2. Find **Port Forwarding** (sometimes under Advanced or NAT)
3. Add two rules:

| Rule name | External port | Internal IP | Internal port | Protocol |
|---|---|---|---|---|
| MacMarket HTTP | 80 | 192.168.1.100 | 80 | TCP |
| MacMarket HTTPS | 443 | 192.168.1.100 | 443 | TCP |

4. Save and apply

> Note: Caddy listens on ports 80 and 443, then proxies to your app internally.
> Your app stays on ports 9500/9510 — those never need to be externally exposed.

---

### Step 3 — Point your domain DNS to your public IP

1. Find your public IP: go to https://whatismyip.com and write it down
2. Go to your domain registrar (where you bought macmarket.io)
3. Go to DNS management
4. Add/update these records:

| Type | Name | Value | TTL |
|---|---|---|---|
| A | @ | your.public.ip.here | 300 |
| A | www | your.public.ip.here | 300 |

5. Save — DNS propagation takes 5 minutes to 48 hours (usually under 30 min)

> Important: Your home IP may change if your ISP uses dynamic IP addresses.
> If macmarket.io stops working after a few days, your IP changed.
> Long-term fix: use a DDNS service like Cloudflare or DynDNS.
> Better fix: move to a VPS (see note at end of guide).

---

### Step 4 — Install and configure Caddy

See the separate **Caddy Reverse Proxy Setup Guide** for full detail.

Quick summary:
1. Download Caddy from https://caddyserver.com/download
2. Create `C:\Caddy\Caddyfile` with your proxy config
3. Run Caddy as a Windows service

Caddy will automatically obtain an SSL certificate from Let's Encrypt 
for macmarket.io the first time it starts. No manual cert work needed.

---

### Step 5 — Create a production Clerk instance

Your current Clerk instance is a **development instance** — it only 
works on localhost. For macmarket.io you need a production instance.

1. Go to https://dashboard.clerk.com
2. Click **Create application** (new, separate from your dev one)
3. Name it "MacMarket Production"
4. Choose your sign-in methods (email, Google, etc.)
5. After creation, go to **Developers → API Keys**
6. Copy your **production** publishable key (`pk_live_...`) and secret key (`sk_live_...`)

Then configure your domain in Clerk:
1. Go to **Domains** in your production Clerk dashboard
2. Add `macmarket.io` as your production domain
3. Clerk will ask you to add a DNS record to verify ownership:
   - Add the CNAME record they specify to your domain registrar
   - Wait for verification (usually a few minutes)

Then configure paths:
1. Go to **Configure → Paths**
2. Set SignIn to: `https://macmarket.io/sign-in`
3. Set SignUp to: `https://macmarket.io/sign-up`
4. Set Signing Out to: `https://macmarket.io/sign-in`
5. Set Fallback development host to: `https://macmarket.io`

---

### Step 6 — Update your .env files

Open `C:\Dashboard\MacMarket-Trader\apps\web\.env.local` and update:

```
# Switch to production Clerk keys
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_live_YOUR_KEY_HERE
CLERK_SECRET_KEY=sk_live_YOUR_SECRET_HERE

# Keep this pointing to backend on localhost
BACKEND_API_ORIGIN=http://127.0.0.1:9510
```

Open `C:\Dashboard\MacMarket-Trader\.env` and update:

```
ENVIRONMENT=production
AUTH_PROVIDER=clerk

# Get these from your production Clerk dashboard → API Keys → JWKS URL
CLERK_JWT_ISSUER=https://clerk.macmarket.io
CLERK_JWKS_URL=https://clerk.macmarket.io/.well-known/jwks.json
CLERK_SECRET_KEY=sk_live_YOUR_SECRET_HERE

# Add your domain to CORS
CORS_ALLOWED_ORIGINS=https://macmarket.io

# Keep existing settings
EMAIL_PROVIDER=resend
RESEND_API_KEY=re_YOUR_KEY
POLYGON_ENABLED=true
POLYGON_API_KEY=YOUR_POLYGON_KEY
```

> The CLERK_JWT_ISSUER URL format for production instances is different from dev.
> Get the exact URLs from your Clerk dashboard → API Keys → show JWT public key → 
> it shows the issuer URL there.

---

### Step 7 — Rebuild the frontend

After changing .env.local, you must rebuild Next.js:

```powershell
cd "C:\Dashboard\MacMarket-Trader\apps\web"
npm run build
```

Then restart both servers:
```powershell
cd "C:\Dashboard\MacMarket-Trader"
.\restart-macmarket-trader.bat
```

---

### Step 8 — Open Windows Firewall ports

Windows Firewall may block inbound connections on ports 80 and 443.

1. Open **Windows Defender Firewall with Advanced Security**
2. Click **Inbound Rules → New Rule**
3. Choose **Port → TCP → Specific ports: 80, 443**
4. Choose **Allow the connection**
5. Apply to all profiles (Domain, Private, Public)
6. Name it "MacMarket External"

---

### Step 9 — Test it

1. From a different device (phone on mobile data, not your home WiFi):
   - Open https://macmarket.io
   - You should see the MacMarket sign-in page with HTTPS padlock
2. Sign in — you should land on the dashboard
3. Check https://macmarket.io/admin/provider-health — verify polygon is live

If the page doesn't load:
- Check Caddy is running: open `http://localhost:2019` (Caddy admin)
- Check DNS has propagated: go to https://dnschecker.org and search macmarket.io
- Check router port forwarding is saved
- Check Windows Firewall rules

---

## PART 3 — Important ongoing considerations

### Dynamic IP problem
Most residential ISPs give you a changing public IP. When it changes, 
macmarket.io stops working. Solutions:
1. **Cloudflare DNS + DDNS client** — free, auto-updates your IP
2. **Move to a VPS** — DigitalOcean/Linode/Hetzner, $5-12/month, 
   static IP, always-on, no router configuration needed

### Keep dev and production separate
- Dev machine: localhost:9500, dev Clerk keys (`pk_test_...`)
- Production: macmarket.io, production Clerk keys (`pk_live_...`)
- Never mix them — keep two separate .env files

### Database backup
Your SQLite DB at `C:\Dashboard\MacMarket-Trader\macmarket_trader.db` 
is your only data store. Back it up regularly:

```powershell
# Run this daily or before any deploy
Copy-Item "C:\Dashboard\MacMarket-Trader\macmarket_trader.db" `
  "C:\Dashboard\MacMarket-Trader\backups\macmarket_trader_$(Get-Date -Format 'yyyyMMdd_HHmmss').db"
```

---

## PART 4 — VPS alternative (recommended for stability)

Running a production app on a home machine has limitations:
- IP changes
- Machine restarts kill the app
- Home internet is less reliable than datacenter

For a more stable setup, consider a $6/month VPS:

1. **DigitalOcean** — create a $6/month Ubuntu droplet
2. SSH in and install Python 3.13, Node 20, Caddy
3. Clone your repo, copy your .env files, deploy
4. Static IP, always-on, professional grade

This is the right move once you start inviting real alpha users.
The deploy script already works on Linux — just change paths.

---

*Save this file to docs/external-access-guide.md in your repo*
