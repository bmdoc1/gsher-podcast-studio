# GSHER Podcast Studio — Cloudflare Pages edition

This subfolder is intentionally isolated from the working Render FastAPI app on `main`.

**Why Pages?** The primary domain `globalselfhealthcare.org` is *not* an active Cloudflare zone. Cloudflare Pages allows connecting the `podcast` subdomain through the existing authoritative DNS provider with a single CNAME record. Changing the domain's nameservers is unnecessary.

**Runtime:** Pages Advanced Mode (`public/_worker.js`), D1 (`DB` binding), private R2 (`MEDIA` binding), and Pages static assets (`ASSETS`, provided automatically). Source must be deployed as a Pages project rooted at this folder, with `public` build output. No Wrangler config with fake database IDs is required. Resource bindings and administrator secrets are configured in the Cloudflare Pages dashboard.

Follow **[SETUP.md](SETUP.md)** exactly. Do not commit API keys, passwords, patient recordings, or photos.

`npm run check` runs five mock integration tests.
