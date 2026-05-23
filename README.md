# Baseline Share

Baseline Share is a project-baseline sharing prototype inspired by 4shared and GitHub. It now includes a local Python backend, SQLite database, sessions, favorites, uploads, ad-gated downloads, and download history.

## Run

```powershell
cd "C:\Users\blank\OneDrive\Desktop\Codex\baseline-share"
python server.py
```

Then open:

```text
http://127.0.0.1:4178
```

## Prototype Features

- Account login saved through a server session cookie
- SQLite database for users, projects, favorites, downloads, ad unlocks, and credits
- Project library with category filters and search
- Favorite projects
- Download history
- Ad-gated downloads when the user has no credits
- Uploading one baseline grants five ad-free download credits
- Ad-free downloads consume one credit

## Production Notes

This is still a local prototype. A real launch will need hosted auth, hosted database, object storage for real zip files, moderation, ad network integration, analytics, abuse prevention, and creator terms.

See `DEPLOYMENT.md` for the launch checklist and the accounts I will need you to authorize.
