# Baseline Share Progress Snapshot

Last updated: 2026-05-21

## Product Idea

Baseline Share is a website where people share reusable base projects. Users can download projects after watching an ad, or upload one useful baseline project to earn five ad-free downloads. Users can create an account, save favorites, and revisit download history.

The design direction is a mix of 4shared and GitHub:

- 4shared-style searchable file/project sharing
- GitHub-style project cards, sidebar navigation, code/project feeling
- Clean, practical, builder-focused marketplace UI

## Current Local URL

Use the backend version now:

```text
http://127.0.0.1:4178
```

Run command:

```powershell
cd "C:\Users\blank\OneDrive\Desktop\Codex\baseline-share"
python server.py
```

The older static prototype used:

```text
http://localhost:4177
```

Do not continue from the static-only version unless needed for comparison.

## Stage 1 Publishing Decision

Use a free hosted URL first, then buy/connect a custom domain later.

Prepared deployment files:

- `render.yaml`
- `railway.json`
- `Procfile`
- `requirements.txt`

Local Git status:

- Git repo initialized in `C:\Users\blank\OneDrive\Desktop\Codex\baseline-share`
- GitHub repo created and pushed:

```text
https://github.com/walkerprocess/baseline-share
```

- Commits pushed to `main`:

```text
d3c8cb1 Initial Baseline Share backend prototype
357bdc5 Add deployment configuration
```

Recommended Stage 1 targets:

- Render free web service, likely `https://baseline-share.onrender.com`
- Railway public service, likely `https://baseline-share.up.railway.app`

Stage 1 deployment completed:

```text
https://baseline-share.onrender.com
```

Verified public endpoints:

```text
https://baseline-share.onrender.com/healthz
https://baseline-share.onrender.com/api/bootstrap
```

External verification results:

- `/healthz` returned `200` with `{"ok": true, "service": "baseline-share"}`
- Home page returned `200`
- Home page contains `<title>Baseline Share</title>`
- `/api/bootstrap` returned 6 seeded projects
- Public stats started clean: 6 projects, 0 downloads, 0 uploads, 0 favorites

Important domain clarification:

- User suggested `baseline.project.share.com`.
- This is not a buyable root domain for us unless we own/control `share.com`.
- It is a nested subdomain under `share.com`.
- Use a platform URL for Stage 1.
- Later buy something like `baselineshare.com`, `baseline-share.com`, `baselineshare.dev`, `sharebaseline.com`, or `getbaseline.dev`.

Current blocker:

- GitHub account is connected as `walkerprocess`.
- Repo exists and code is pushed.
- Render Blueprint is connected and deployed.
- Current public Stage 1 URL is live at `https://baseline-share.onrender.com`.

## Important Files

- `index.html` - main UI shell
- `styles.css` - visual design
- `app.js` - frontend logic connected to backend APIs
- `server.py` - Python backend, API routes, static file server
- `baseline_share.db` - local SQLite database, ignored by git
- `.gitignore` - ignores DB and Python cache files
- `README.md` - user-facing run notes
- `DEPLOYMENT.md` - real web launch/auth checklist
- `baseline-share-preview.png` - previous UI preview screenshot

## Backend Status

The app now has a real local backend instead of browser-only `localStorage`.

Backend stack:

- Python standard library only
- `ThreadingHTTPServer`
- SQLite database
- Session cookie auth
- Static frontend served by the same server

Database tables:

- `users`
- `sessions`
- `projects`
- `favorites`
- `downloads`
- `ad_unlocks`

Seed projects are inserted automatically when the DB is initialized:

- React SaaS Dashboard
- FastAPI Auth Starter
- Analytics Pipeline Kit
- RAG Chatbot Baseline
- Encrypted Chatroom
- Product Roadmap Workspace

## Implemented API Routes

- `GET /api/bootstrap`
  - Returns current user, credits, projects, favorites, downloads, stats.
- `POST /api/auth/login`
  - Creates or updates a user by email and creates a session cookie.
- `POST /api/auth/logout`
  - Deletes session and expires cookie.
- `POST /api/projects`
  - Requires login. Creates uploaded project and grants 5 credits.
- `POST /api/favorites/toggle`
  - Requires login. Adds/removes favorite.
- `POST /api/downloads/start`
  - Requires login.
  - If user has credits: consumes 1 credit and records download.
  - If user has no credits: creates ad unlock token.
- `POST /api/downloads/complete-ad`
  - Requires login.
  - Enforces 5 second sponsor view before recording download.
- `GET /api/projects/:id/manifest`
  - Downloads a text manifest placeholder.
  - Production should stream a real project archive from object storage.

## Verified Flows

Verified by direct HTTP/API session:

- New user login works.
- Session cookie works.
- Projects load from SQLite.
- Favorite toggles save to DB.
- Download with zero credits requires ad unlock.
- Ad completion records download after waiting.
- Upload grants 5 credits.
- Credit download consumes 1 credit.
- Download count and credits update correctly after commit timing fix.
- Curated Codex projects now download as real `.zip` files.
- User uploads now require an actual `.zip` file before credits are granted.
- Multipart upload was verified with a student-user test: login, zip upload, 5 credits, zip re-download, and `PK` zip header check.

Verified in browser:

- App loads at `http://127.0.0.1:4178`.
- Six project cards render from backend.
- Stats start clean: 6 baselines, 0 downloads, 0 uploads, 0 favorites.
- No browser console errors during final clean load.

## Known Notes

- The local DB may contain smoke-test users/projects from upload verification. The DB is ignored by git and not pushed.
- Browser automation text entry had an environment-specific clipboard issue, so backend logic was verified through direct API requests.
- Current auth is email/name demo auth. It is not production-grade.
- Curated projects and user-uploaded projects can download actual zip files.
- Seed projects without a real archive still fall back to a manifest download.
- Uploaded files are stored on local/Render app filesystem for Stage 1. This can reset on redeploy, so object storage is still needed before serious production traffic.

## Production Gaps

Before public launch, upgrade these:

- Real auth: password, OAuth, or magic link.
- Hosted database, preferably Postgres.
- Object storage for uploaded zip files.
- Moderation queue before uploads become public.
- Signed download URLs to prevent scraping.
- Real ad network integration.
- Terms of service and upload license agreement.
- Abuse/rate limiting.
- Admin dashboard for reviewing uploads.

## Auth Needed From User Later

No auth is needed for local backend work right now.

For real web deployment, ask user to authorize/log in to:

- GitHub, if creating/pushing a new `baseline-share` repository.
- Hosting platform account, such as Render, Railway, Fly.io, or another chosen host.
- Domain/DNS provider only if using a custom domain.
- Ad network account later, because monetized ads require the user's own approved account.

## Next Best Steps

1. Add real project archive upload support.
2. Add local file storage first, then later move to object storage.
3. Add project detail page or modal.
4. Add upload review/moderation status.
5. Push this folder as its own GitHub repository.
6. Deploy the backend prototype publicly.
7. Start importing projects from `C:\Users\blank\OneDrive\Desktop\Codex\projects`.

## User Goal After Backend

After backend and real web deployment, start posting the projects already made in the Codex folder:

- `projects\01-encrypted-chatroom`
- `projects\02`
- `projects\03-jobfit-resume-intelligence`

Eventually these should become real downloadable baseline projects on Baseline Share.

Current status:

- `01-encrypted-chatroom` is packaged as `assets/project-zips/encrypted-chatroom.zip`
- `02` is packaged as `assets/project-zips/live-logistics-news-analytics.zip`
- `03-jobfit-resume-intelligence` is packaged as `assets/project-zips/jobfit-resume-intelligence.zip`
- These are seeded in the app as resume/portfolio-ready downloadable projects.
