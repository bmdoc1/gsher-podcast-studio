# GSHER Podcast Studio

Public listening library and private episode editor for Global Self-Healthcare Education & Research (GSHER).

## Release status
The GitHub repository has been created, but the complete application source is **not yet present in this repository**. **Do not deploy** until the source files in `GSHER_Podcast_Studio_Deployment_Ready_v2.zip` have been extracted and uploaded to the repository root.

## Prepare the code
1. Download the V2 ZIP from the ChatGPT conversation where this repository was set up.
2. Extract the archive, then open the inner `gsher-podcast-studio` directory.
3. Upload its contents, including `app.py`, `static/`, `Dockerfile`, `requirements.txt`, and `render.yaml`, to the **repository root**, replacing these setup-only instructions as needed.
4. Do not commit `.env`, recordings, personal data, or credentials.

## Deploy on Render
Use **New → Blueprint** and select this repository. Its `render.yaml` requests a paid Starter web service and a persistent 10-GB disk for audio, images, and the SQLite database. Review and approve any charges before creating the service. Set a strong `ADMIN_PASSWORD` using Render's secret environment variable settings. Never store a real password in Git.

First verify the Render-generated HTTPS URL, `/health`, administrator login, draft privacy, upload, and playback. After verification, configure `podcast.globalselfhealthcare.org` as a custom domain with a DNS CNAME to the hostname supplied by Render.

Do not change the existing GSHER main website, Learning Academy, or Odia Pathasala until this standalone service is verified. Only then add the navigation link.

See the original deployment guide in the downloadable ZIP for complete security and transcription configuration.
