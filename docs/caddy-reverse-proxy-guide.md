# Caddy Reverse Proxy Setup Guide
# For MacMarket Trader on Windows with macmarket.io

Last updated: April 2026

---

## What is Caddy and why use it

Caddy is a modern web server that acts as a reverse proxy — it sits 
in front of your app and handles:

- **Automatic HTTPS** via Let's Encrypt (free SSL certificates, 
  auto-renewed, zero configuration)
- **Routing** — sends requests for macmarket.io to your Next.js app 
  on port 9500 and API calls to FastAPI on port 9510
- **HTTP → HTTPS redirect** automatically
- **Security headers** out of the box

Without Caddy (or similar), Clerk will refuse to work on your domain 
because it requires HTTPS, and browsers will show "not secure" warnings.

---

## PART 1 — Install Caddy on Windows

### Step 1 — Download Caddy

1. Go to https://caddyserver.com/download
2. Select:
   - **Platform:** Windows
   - **Architecture:** amd64 (for most modern PCs)
   - No extra plugins needed for basic use
3. Click **Download**
4. You'll get a file called `caddy_windows_amd64.exe`

### Step 2 — Set up the Caddy folder

Open PowerShell as Administrator and run:

```powershell
# Create Caddy directory
New-Item -ItemType Directory -Path "C:\Caddy" -Force

# Move the downloaded exe there
Move-Item "$env:USERPROFILE\Downloads\caddy_windows_amd64.exe" "C:\Caddy\caddy.exe"

# Create config and log directories
New-Item -ItemType Directory -Path "C:\Caddy\logs" -Force
New-Item -ItemType Directory -Path "C:\Caddy\data" -Force
```

### Step 3 — Verify Caddy works

```powershell
cd "C:\Caddy"
.\caddy.exe version
```

You should see something like `v2.x.x`. If you get an error, make 
sure the exe downloaded correctly.

---

## PART 2 — Create the Caddyfile

The Caddyfile is Caddy's configuration. Create it at `C:\Caddy\Caddyfile`.

Open Notepad as Administrator and save this as `C:\Caddy\Caddyfile` 
(no extension):

```
# MacMarket Trader - Caddy reverse proxy configuration

# Redirect www to non-www
www.macmarket.io {
    redir https://macmarket.io{uri} permanent
}

# Main site
macmarket.io {
    # Caddy automatically obtains and renews SSL cert from Let's Encrypt
    # No manual certificate work needed

    # Security headers
    header {
        Strict-Transport-Security "max-age=31536000; includeSubDomains"
        X-Content-Type-Options "nosniff"
        X-Frame-Options "SAMEORIGIN"
        Referrer-Policy "strict-origin-when-cross-origin"
        -Server
    }

    # API routes go to FastAPI backend on port 9510
    # This covers /health, /user/*, /admin/* backend routes
    @backend path /health /user/* /admin/* /docs /openapi.json
    reverse_proxy @backend 127.0.0.1:9510 {
        header_up Host {upstream_hostport}
        header_up X-Real-IP {remote_host}
        header_up X-Forwarded-For {remote_host}
        header_up X-Forwarded-Proto {scheme}
    }

    # Everything else goes to Next.js frontend on port 9500
    reverse_proxy 127.0.0.1:9500 {
        header_up Host {upstream_hostport}
        header_up X-Real-IP {remote_host}
        header_up X-Forwarded-For {remote_host}
        header_up X-Forwarded-Proto {scheme}
    }

    # Logging
    log {
        output file C:/Caddy/logs/access.log {
            roll_size 50mb
            roll_keep 5
        }
        format json
    }
}
```

> Important: The @backend matcher routes direct API calls to FastAPI.
> Next.js also proxies API calls internally via its route handlers —
> the @backend rule here is for direct backend access and health checks.

---

## PART 3 — Test the Caddyfile locally first

Before going live, test that Caddy can parse your config:

```powershell
cd "C:\Caddy"
.\caddy.exe validate --config Caddyfile
```

You should see:
```
Valid configuration
```

If you see errors, they'll point to the exact line with the problem.

---

## PART 4 — Run Caddy as a Windows Service

Running Caddy manually means it stops when you close the terminal. 
Install it as a Windows service so it starts automatically on boot.

### Step 1 — Install the service

In PowerShell as Administrator:

```powershell
cd "C:\Caddy"

# Install Caddy as a Windows service
.\caddy.exe service install --config C:\Caddy\Caddyfile --envfile C:\Caddy\caddy.env

# Start the service
.\caddy.exe service start
```

### Step 2 — Create the environment file

Create `C:\Caddy\caddy.env` (Caddy reads this for environment variables):

```
CADDY_AGREE_TO_TERMS=true
```

This auto-accepts the Let's Encrypt terms of service.

### Step 3 — Verify the service is running

```powershell
# Check service status
Get-Service -Name caddy

# Should show: Status: Running
```

Or open **Services** (Win+R → services.msc) and find "Caddy Web Server".

---

## PART 5 — First startup and SSL certificate

The first time Caddy starts with your domain configured:

1. It sends an HTTP challenge to Let's Encrypt to verify you own macmarket.io
2. Let's Encrypt checks that macmarket.io points to your IP (DNS must be set)
3. Let's Encrypt issues a free SSL certificate
4. Caddy installs and starts using it automatically
5. Caddy auto-renews it before it expires (every 90 days)

**This only works if:**
- Your DNS A record for macmarket.io points to your public IP ✓
- Port 80 is open on your router and Windows Firewall ✓
- Port 443 is open on your router and Windows Firewall ✓

If DNS isn't set yet when Caddy starts, it will retry automatically 
every few minutes until it succeeds.

---

## PART 6 — Verify everything is working

### Check Caddy admin API
```powershell
# Caddy exposes an admin API on port 2019 (local only)
Invoke-WebRequest -Uri "http://localhost:2019/config/" -UseBasicParsing
```

### Check SSL certificate status
```powershell
Invoke-WebRequest -Uri "http://localhost:2019/pki/ca/local" -UseBasicParsing
```

### Check access logs
```powershell
Get-Content "C:\Caddy\logs\access.log" -Tail 20
```

### Test from outside
From your phone on mobile data (not home WiFi):
```
https://macmarket.io/health
```
Should return: `{"status":"ok","service":"macmarket-trader"}`

---

## PART 7 — Useful Caddy commands

All run from `C:\Caddy` in PowerShell as Administrator:

```powershell
# Reload config without restart (after editing Caddyfile)
.\caddy.exe reload --config Caddyfile

# Stop the service
.\caddy.exe service stop

# Start the service
.\caddy.exe service start

# Restart the service
.\caddy.exe service restart

# Uninstall the service (if needed)
.\caddy.exe service uninstall

# View current running config
.\caddy.exe service status

# Test config file syntax
.\caddy.exe validate --config Caddyfile
```

---

## PART 8 — Troubleshooting

### "Site can't be reached" from outside
1. Check router port forwarding is saved (80 and 443 to your machine's local IP)
2. Check Windows Firewall — inbound rules for ports 80 and 443
3. Check DNS has propagated: https://dnschecker.org → search macmarket.io
4. Check Caddy is running: `Get-Service -Name caddy`
5. Check Caddy logs: `Get-Content "C:\Caddy\logs\access.log" -Tail 50`

### "SSL certificate error" in browser
- Wait 5 minutes — certificate issuance takes time on first startup
- Check port 80 is open (Let's Encrypt needs port 80 for the challenge)
- Check Caddy logs for `certificate` or `ACME` errors

### Caddy service won't start
```powershell
# Run Caddy in foreground to see full error output
cd "C:\Caddy"
.\caddy.exe run --config Caddyfile
```
This shows all errors directly in the terminal.

### "Connection refused" to backend/frontend
- Make sure your MacMarket app is actually running (backend on 9510, frontend on 9500)
- Caddy forwards requests but can't start your app — run the deploy script first

### Let's Encrypt rate limits
Let's Encrypt allows 5 certificate requests per domain per week.
If you hit this limit during testing, use Caddy's staging environment:
Add `acme_ca https://acme-staging-v02.api.letsencrypt.org/directory` 
inside your `macmarket.io { }` block for testing.
Remove it for production.

---

## PART 9 — Caddyfile for local dev (no domain needed)

If you want to test Caddy locally before going live with the real domain:

```
# Local test config — saves to C:\Caddy\Caddyfile.local
localhost:8443 {
    tls internal  # self-signed cert for local testing

    @backend path /health /user/* /admin/*
    reverse_proxy @backend 127.0.0.1:9510

    reverse_proxy 127.0.0.1:9500
}
```

Run with:
```powershell
.\caddy.exe run --config Caddyfile.local
```

Your app will be at https://localhost:8443 (browser will warn about 
self-signed cert — click Advanced → Proceed).

---

## PART 10 — When you move to a VPS

On a Linux VPS (Ubuntu), Caddy setup is even simpler:

```bash
# Install Caddy
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update
sudo apt install caddy

# Edit config
sudo nano /etc/caddy/Caddyfile

# Restart
sudo systemctl restart caddy
sudo systemctl enable caddy  # auto-start on boot
```

The Caddyfile content is identical — just copy it over.

---

*Save this file to docs/caddy-reverse-proxy-guide.md in your repo*
