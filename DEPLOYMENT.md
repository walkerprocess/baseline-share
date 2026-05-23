# Baseline Share Deployment Notes

## Current Backend

- Python standard-library server in `server.py`
- SQLite database in `baseline_share.db`
- Session cookie auth
- API routes for projects, uploads, favorites, downloads, ad unlocks, and credits
- Static frontend served from the same app

## Local Run

```powershell
cd "C:\Users\blank\OneDrive\Desktop\Codex\baseline-share"
python server.py
```

Open:

```text
http://127.0.0.1:4178
```

## Stage 1 Recommendation

Start with a free hosting URL before buying a domain.

Recommended first deployment:

- Render free web service: likely URL format `https://baseline-share.onrender.com`
- Railway public service: likely URL format `https://baseline-share.up.railway.app`

Current deployment prep files:

- `render.yaml` for Render Blueprint deployment
- `railway.json` for Railway deployment
- `Procfile` for platform start command compatibility
- `requirements.txt` because the backend currently has no third-party Python dependencies

The backend must bind to:

```text
0.0.0.0:$PORT
```

`server.py` already supports this through `HOST` and `PORT` environment variables.

## Domain Note

`baseline.project.share.com` cannot be used unless we own or control `share.com`.

That name is a subdomain chain:

```text
baseline.project.share.com
```

Meaning:

- root domain: `share.com`
- subdomain: `project.share.com`
- nested subdomain: `baseline.project.share.com`

If we do not own `share.com`, we cannot create that DNS record.

Better future domain options:

- `baselineshare.com`
- `baseline-share.com`
- `baselineshare.dev`
- `sharebaseline.com`
- `getbaseline.dev`

## Real Web Auth I Will Need From You

To put this on the real web, I will need you to log in or authorize these from the browser when we reach that step:

- GitHub account access, if we create/push a new `baseline-share` repository
- Hosting account access, such as Render, Railway, Fly.io, or another platform you choose
- Domain/DNS access only if you want a custom domain
- Ad network account access later, because real ad monetization requires your account and approval

## Production Upgrade Path

SQLite is fine for the local prototype, but before public launch we should move to:

- Hosted Postgres for user/project/download data
- Object storage for real uploaded project zip files
- Real auth with password, OAuth, or magic links
- Moderation queue before uploaded projects become public
- Signed download URLs so files cannot be scraped
- Terms of service and upload license agreement
- Ad network integration after the product has acceptable content and traffic

## Ads And Monetization

Current status:

- The download flow has a sponsor-view gate.
- Real ad revenue is not active yet because ad networks require account approval and publisher IDs.
- `/ads.txt` is implemented and can be configured later with the `ADS_TXT_CONTENT` environment variable.

Recommended path:

1. Keep the demo sponsor gate while testing the product.
2. Add real content pages and project detail pages so the site has enough original content for review.
3. Apply for Google AdSense after the site has a real domain and useful content.
4. If the audience becomes developer/student focused, also apply for Carbon Ads or BuySellAds sponsorships.
5. After approval, set `ADS_TXT_CONTENT` in Render using the exact line from the ad network.

Do not add fake publisher IDs. Use only approved ad network code from the user's account.
