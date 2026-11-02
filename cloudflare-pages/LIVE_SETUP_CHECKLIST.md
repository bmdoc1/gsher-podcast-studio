# GSHER Podcast Studio — Cloudflare account setup

Provided Pages URL: https://gsher-podcast-studio.pages.dev/

**Status:** URL supplied by GSHER; external HTTP verification was unavailable from the assistant's network. Do not call this a fully validated deployment until staging tests pass.

## Cloudflare dashboard actions

1. Create a **D1** database named `gsher-podcast-db` under the same Cloudflare account as this Pages project. In its SQL console execute the statements in [schema.sql](schema.sql). Check that tables `episodes`, `upload_sessions`, and `login_attempts` exist.
2. Create an **R2** bucket named `gsher-podcast-media` in the same account. Keep it **private**, without a public `r2.dev` or custom-domain URL. R2 activation may require billing setup even if usage stays within the free tier.
3. In the **Pages project** `gsher-podcast-studio` → Settings → Bindings, add D1 binding variable **`DB`** to `gsher-podcast-db` and R2 bucket binding variable **`MEDIA`** to `gsher-podcast-media`. Ensure these bind to **Production**.
4. Under Settings → Variables and Secrets, add encrypted **`ADMIN_PASSWORD`** (unique password 24+ characters) and **`SESSION_SECRET`** (independent 32+ bytes of randomness). Do not reuse the Render credentials or commit secrets to Git. Optional `OPENAI_API_KEY` is not needed for manual transcripts.
5. Redeploy production after updating bindings/secrets, using the project Deployments tab. Verify [health](https://gsher-podcast-studio.pages.dev/health) returns `{"ok":true,"platform":"cloudflare"}`; verify [session](https://gsher-podcast-studio.pages.dev/api/session) shows `"password_configured":true` and `"admin":false` before sign-in.
6. Test private draft, non-sensitive audio upload and playback, speaker-photo upload, edit transcript, publication and unpublication. Confirm draft media URLs return 404 in an incognito browser before publication and after unpublication.
7. **Only after tests pass:** Pages project → Custom domains → Set up a domain `podcast.globalselfhealthcare.org`. In the existing authoritative DNS provider create/update ONLY the `podcast` CNAME to `gsher-podcast-studio.pages.dev` as instructed by Cloudflare. No root/website/email/nameserver changes.

## Protections

- Do not transfer `globalselfhealthcare.org` nameservers or add it as a Cloudflare zone merely for this Pages subdomain.
- Keep `@`, `www`, `learn`, MX, SPF/DKIM/DMARC and other existing DNS entries unchanged.
- Keep Render `main` branch and preview service available until Cloudflare production has passed end-to-end tests.
- Do not upload identifiable patient information. Obtain speaker/photography permission.

Cloudflare official documentation: https://developers.cloudflare.com/pages/functions/bindings/ and https://developers.cloudflare.com/pages/configuration/custom-domains/ .
