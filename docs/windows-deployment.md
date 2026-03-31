# Windows Deployment

Scripts are under `scripts/` and assume host path `C:\Dashboard\MacMarket-Trader`.

## Files

- `deploy_windows.bat`: pull/reset, mirror live dir, install deps, build frontend, run migrations/tests, start services.
- `restart_windows.bat`: restart services on configured ports only.
- `run_backend_dev_windows.bat`: local backend dev server.
- `run_frontend_dev_windows.bat`: local frontend dev server.

## Ports

- Frontend: `9500`
- Backend API (when frontend exists): `9510`
- Backend-only mode fallback: `9500`
