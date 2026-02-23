# Azure App Service Deployment (sqlfromllm)

## 1) Recommended hosting choice
- Use **Azure App Service (Linux, Python 3.11/3.12)**.
- Your app runs on `python server.py` and listens on `PORT`.

## 2) Required files (already in repo)
- `requirements.txt`
- `startup.sh`
- `azure.appsettings.sample`
- health endpoint in `server.py`: `GET /health` (or `GET /api/health`)

## 3) App Service configuration
In **App Service -> Configuration -> Application settings**, add:
- `FABRIC_TENANT_ID`
- `FABRIC_CLIENT_ID`
- `FABRIC_CLIENT_SECRET`
- `FABRIC_SQL_ENDPOINT`
- `FABRIC_DATABASE`
- `GEMINI_API_KEY`

Optional:
- `PORT` = `8000`

## 4) Startup command
In **App Service -> Configuration -> General settings -> Startup Command**:

```bash
bash startup.sh
```

## 5) Deploy
## Option A: Local Git / ZIP deploy
- Push this folder to App Service deployment source.

## Option B: GitHub Actions (recommended)
- Connect repo in Deployment Center.
- Use Python workflow and deploy on push to main.

## 6) Verify after deploy
- Health:
  - `https://<your-app>.azurewebsites.net/health`
  - expect: `{"status":"ok","service":"sqlfromllm"}`
- API smoke:
  - `POST /api/intent`
  - `POST /api/sql_from_intent`
  - `POST /api/sql`

## 7) Operational checklist
- Do not keep secrets in `.env` in repo.
- Use TLS only (default on Azure).
- Restrict access (Easy Auth / Microsoft Entra ID) if internal users only.
- Enable logs + App Insights.

## 8) If pyodbc fails on built-in Linux runtime
If you see `ModuleNotFoundError: pyodbc` or SQL driver errors, deploy as a custom container.

Use included `Dockerfile` (installs `msodbcsql18`).

High-level steps:
1. Build and push image to ACR.
2. Configure App Service to use that image.
3. Keep app settings (`FABRIC_*`, `GEMINI_API_KEY`) in App Service Configuration.
