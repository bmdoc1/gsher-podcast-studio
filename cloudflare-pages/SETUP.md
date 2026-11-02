# GSHER Podcast Studio — safe Cloudflare Pages rollout

**Deployment stage:** Source committed to `cloudflare-migration`; Cloudflare account resources are NOT created by this package. **Do not change existing nameservers, MX, SPF, DKIM, DMARC, website, Academy, or `learn` subdomain records.** Keep the current Render preview on GitHub `main` until this deployment has been tested.

This edition uses **Cloudflare Pages Advanced Mode** (`public/_worker.js`) with the existing podcast interface and three Cloudflare services: Pages (frontend + API), D1 (episode catalogue and transcripts) and private R2 (recordings and images). Cloudflare officially permits custom *subdomains* on Pages while the main domain stays with a third-party DNS provider: https://developers.cloudflare.com/pages/configuration/custom-domains/ .

## 1. Connect Pages to GitHub: no main-domain changes

At https://dash.cloudflare.com/ open **Workers & Pages → Create application → Pages → Connect to Git**. Grant Cloudflare access to the GitHub repo `bmdoc1/gsher-podcast-studio`, if asked.

Use the following **exact** values:

| Setting | Value |
|---|---|
| Project name | `gsher-podcast-pages` (or another available name) |
| Repository | `bmdoc1/gsher-podcast-studio` |
| Production branch | `cloudflare-migration` |
| Root directory (advanced) | `cloudflare-pages` |
| Framework | None |
| Build command | `exit 0` |
| Build output directory | `public` |

Deploy to the temporary `<actual-project-name>.pages.dev` URL **first**. The visual interface should load even before resources are bound; data API routes will return HTTP 503 until D1 and R2 are configured. Do not connect your domain at this stage.

## 2. Create private storage and database

In the same Cloudflare account:

- Go to **R2 Object Storage**, activate it if necessary (Cloudflare may require billing details), and create bucket `gsher-podcast-media`. Keep it **private**. Do not enable a public `r2.dev` URL or public custom domain for the bucket.
- Go to **Workers & Pages → D1**, create database `gsher-podcast-db`, and execute the SQL in `cloudflare-pages/schema.sql` using the D1 SQL console. The statements are idempotent, but review them before applying.
- Open your Pages project → **Settings → Bindings**. Add **D1** binding variable `DB` pointing to `gsher-podcast-db`, and **R2 bucket** binding variable `MEDIA` pointing to `gsher-podcast-media`. Apply to the production environment; configure preview separately if using it. Redeploy after adding bindings.

The code intentionally stores all uploads privately in R2; media requests go through the publication status check in D1. The free Render preview is not migrated automatically and its ephemeral data should not be considered a durable backup.

## 3. Set administrator secrets (Cloudflare only)

Under the Pages project **Settings → Variables and Secrets**, configure encrypted values (not plain text committed to Git):

- `ADMIN_PASSWORD`: new unique random password of at least 24 characters; **do not reuse** the Render password.
- `SESSION_SECRET`: independently generated random string of at least 32 bytes.
- `OPENAI_API_KEY` (optional): only for AI transcription and draft briefings, with provider charges and explicit speaker/recording permissions.

Follow the dashboard instructions to redeploy. Missing administrator credentials **disable** admin sign-in. Do not paste credentials in GitHub, a public issue, or chat. Use a trusted password manager.

## 4. Staging checks on pages.dev (before DNS change)

1. Check `/health` returns `{"ok":true,"platform":"cloudflare"}`.
2. Check `/api/session` shows `password_configured:true`, `admin:false` when signed out.
3. Log into Studio; create a **draft** test episode and upload a non-sensitive test MP3 and test speaker photo.
4. In another/private browser window verify the draft and its direct media URL are inaccessible (HTTP 404).
5. Publish it and check that the recording plays; return it to Draft and confirm the recording URL becomes inaccessible again.
6. Test multi-part upload with a non-sensitive audio file >24MB and edit an Odia transcript. Verify recordings remain present across a Pages redeploy.
7. Confirm all public and admin features work over HTTPS before updating DNS.

## 5. Connect ONLY the podcast subdomain

At the successful Pages project, go to **Custom domains → Set up a domain** and enter:

`podcast.globalselfhealthcare.org`

Cloudflare will show the **actual** Pages hostname such as `gsher-podcast-pages.pages.dev`. At your **current authoritative DNS provider** (not necessarily the domain registrar), create or, if a `podcast` CNAME already exists, carefully replace **only** the existing `podcast` record:

| DNS field | Value |
|---|---|
| Type | `CNAME` |
| Host / Name | `podcast` |
| Target | the **actual hostname** Cloudflare Pages displays, e.g. `gsher-podcast-pages.pages.dev` |
| TTL | 300 / Auto |

**Do not edit:** nameservers, `@` or `www`, `learn`, `MX`, `TXT` (SPF/DMARC), DKIM, CAA, verification records or other subdomains. Do **not** add `globalselfhealthcare.org` as a zone solely for this subdomain. After DNS propagation, verify custom domain and HTTPS in Pages. Cloudflare Pages documentation: https://developers.cloudflare.com/pages/configuration/custom-domains/ .

If you cannot locate the authoritative DNS panel, stop without changing records. Neither Render nor Cloudflare Pages needs to replace the existing website.

## Limitations and care requirements

- The code package is tested locally, **not yet tested in your Cloudflare account**. Do not claim it is live until an actual Pages deployment succeeds.
- Video is uploaded and served as original files, without adaptive encoding. Consider paid video encoding/streaming later.
- AI transcription handles eligible audio files under 24 MiB. For video or lengthy content, upload your edited `.txt/.srt/.vtt` transcript or add a dedicated audio-processing service. AI output requires review, especially for Odia/Hindi and medical content.
- Ensure informed speaker consent and permission for photographs/recordings. Avoid identifiable patient medical data. Verify all clinical statements before publication.
- D1 and R2 billing/free allowances can change; review Cloudflare plan details before enabling R2.
- Back up D1 and R2 before major content changes; use least-privilege Cloudflare account access.

## Local test command

`cd cloudflare-pages && npm run check`

This tests the API workflows with mock D1/R2 and validates JavaScript syntax, but it does not replace live staging checks.
