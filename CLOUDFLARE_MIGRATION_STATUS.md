# GSHER Podcast Studio — Cloudflare migration staging

The `cloudflare-migration` branch is a staging branch; the active Render preview is deployed from `main` and must remain unchanged.

## Source package
A tested Cloudflare Worker/D1/R2 migration package is available in the associated ChatGPT conversation as **GSHER_Podcast_Cloudflare_Migration.zip**.

The source archive contains:
- `cloudflare/src/index.js`: Worker API compatible with the existing podcast interface
- `cloudflare/public/`: GSHER web interface
- `cloudflare/schema.sql`: D1 schema
- `cloudflare/wrangler.jsonc`: Worker configuration
- `cloudflare/CLOUDFLARE_SETUP.md`: setup and safety guide
- `cloudflare/tests/`: local API/mock regression checks

**Not yet deployed to Cloudflare.** Do not connect a production Worker or change podcast DNS until those source files are committed to this branch, D1/R2 resources and secrets are configured, and publication/privacy tests pass on a temporary workers.dev URL.

Do not put administrator passwords, Cloudflare API tokens, or patient recordings into this public repository.
