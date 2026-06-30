# Deploying SpectraCardio (free)

The FastAPI service serves **everything from one process** — the React UI, the
JSON API, and the interactive `/docs`. So a single free deployment gives you the
whole stack at one URL.

> Research/educational demo — not a clinical system.

## Recommended: Render (full stack, free, one Blueprint)

The repo ships a `render.yaml` Blueprint, so Render configures itself.

1. Push the repo to GitHub (see below).
2. Go to **https://render.com** and sign in with GitHub (free).
3. Click **New +  →  Blueprint**.
4. Select your **SpectraCardio** repo. Render reads `render.yaml` and shows a
   service named `spectracardio` on the **Free** plan.
5. Click **Apply**. Render installs `requirements-api.txt` and starts the app.
6. After a few minutes you get a live URL like
   **`https://spectracardio.onrender.com`**:
   - `/`        → the React dashboard (frontend)
   - `/docs`    → interactive API docs (backend)
   - `/health`  → status

That single URL is the one to put on your resume / LinkedIn.

**Free-tier notes (be aware, not problems):**
- The service **sleeps after ~15 min idle**; the next visit takes ~30–60 s to
  wake. Normal for free hosting.
- No trained model is committed, so the API uses the transparent **logistic
  fallback** scorer. To serve the Random Forest, run `python src/train_model.py`
  and commit `outputs/rf_model.joblib` (remove it from `.gitignore` first).

## Alternative hosts (same app)

- **Railway** / **Fly.io** — both detect the `Dockerfile`; the image honors `$PORT`.
- **Docker anywhere**: `docker compose up --build` → `http://localhost:8000`.

## Frontend-only options (no backend)

If you only want the static dashboard live (no API):

- **GitHub Pages:** repo **Settings → Pages → Source: `main`, folder `/ (root)`**.
  Live at `https://<user>.github.io/SpectraCardio/`.
- **Vercel:** import the repo, Framework **Other**, no build command, output dir
  `.` → `*.vercel.app` URL that auto-redeploys on every push.

## Streamlit version (interactive Python app)

Deploy `streamlit_app.py` free on **https://share.streamlit.io** (sign in with
GitHub → New app → pick the repo and `streamlit_app.py`). The Live Monitor's
"Synthetic demo" works on the cloud with no data download.
