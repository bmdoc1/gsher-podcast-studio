# GSHER Podcast Studio

A lightweight self-hosted web application for **Global Self-Healthcare Education & Research (GSHER)**. It keeps the public listening library separate from the password-protected editorial studio.

## Features

- Public responsive episode library at `/` with search and English / Hindi / Odia filters.
- Audio (MP3, M4A, WAV, OGG) and video (MP4, WEBM, MOV) uploads and playback.
- Up to eight speakers per episode with name, designation and individual photo.
- Episode title, series, date, language and editorial briefing/key takeaways.
- Optional AI-assisted *draft* episode briefing from a saved transcript when a separate API key is configured (editor must verify and save).
- Editable transcript text or import of UTF-8 `.txt`, `.srt` or `.vtt` files.
- Clickable transcript timestamps for audio/video seek when transcripts use `[hh:mm:ss] ...`, SRT or VTT formats.
- Draft vs. Published visibility, deletion, full-text episode search, transcript download.
- Optional audio/video automatic transcription through the OpenAI Speech-to-Text API (server API key required) or `faster-whisper` (server CPU required). Human verification remains necessary for all languages; particularly Odia, mixed-language material and medical terminology.

**Deployment-ready v2:** includes `render.yaml`, `Dockerfile`, `DEPLOYMENT.md` and the GSHER homepage integration snippet. The studio is not publicly deployed until the hosting, DNS and GSHER navigation steps are completed.

## Quick local setup (Python 3.10+)

```bash
cd gsher-podcast-studio
python -m venv .venv
source .venv/bin/activate    # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
export ADMIN_PASSWORD='choose-a-long-unique-password'
export SESSION_SECRET='paste-a-random-64-character-secret'
uvicorn app:app --host 127.0.0.1 --port 8000
```

Visit `http://127.0.0.1:8000`, then select **Studio admin** and sign in. On Windows PowerShell, use `$env:ADMIN_PASSWORD="..."` and `$env:SESSION_SECRET="..."` instead of `export`.

1. Create a new draft episode and supply its title, date, language and a plain-language briefing.
2. Save the draft, upload an audio or video recording and a cover image.
3. Add speakers and photographs, then save speaker entries.
4. Paste a reviewed transcript or upload UTF-8 text / SRT / VTT.
5. Change visibility from Draft to Published and save. The episode immediately appears in the public library.

## Optional automatic transcription

For cloud transcription, configure `OPENAI_API_KEY` and install FFmpeg (included in the Docker deployment). The audio track is sent to the external transcription service and may incur fees. For offline local transcription, install FFmpeg in the operating system, then run `pip install faster-whisper` and do not set `OPENAI_API_KEY`. The Studio's **Transcribe uploaded recording** button will generate a time-stamped draft transcript on the server. Set `WHISPER_MODEL=small` (default), `base`, `medium` or another supported Whisper model depending on available memory. The first run may need to download model files. Processing a long programme can take considerable CPU time. For Hindi/Odia/English code-mixing and specialist terms, manually check names, drug doses, clinical claims and all wording before publishing.

**Automatic speaker identification is not included:** speakers' names and portraits are added manually. It is **not** safe to infer the identity of a speaker from their voice or their photograph alone.

## Optional AI-generated episode briefing

Set `OPENAI_API_KEY` as a server-side environment secret and optionally `BRIEF_MODEL=gpt-4o-mini`. After creating and saving a transcript, use **Generate AI briefing draft**, review the generated wording carefully, and explicitly save it. The backend uses the OpenAI API **separately from any ChatGPT subscription**. API charges may apply, and transcript text is sent to the configured model service. Obtain all appropriate consents and avoid sending identifiable patient information. If no API key is supplied, the manual editorial briefing remains fully functional.

## Website integration

See **`DEPLOYMENT.md`** for exact instructions to deploy on Render with persistent storage, configure the dedicated subdomain and add a navigation link without changing any other GSHER website features.


Suggested dedicated public location: `podcast.globalselfhealthcare.org`. Deploy the app to a Python-capable host or VPS with HTTPS and reverse proxy, and add **GSHER Podcasts** to the existing homepage navigation. Alternatively, embed it in an iframe on a GSHER page:

```html
<iframe src="https://podcast.globalselfhealthcare.org/" title="GSHER Podcast Studio" style="width:100%;height:1000px;border:0" loading="lazy"></iframe>
```

**Important:** This package does not make any changes to the currently live GSHER, Academy, blog, or Odia Pathasala sites. It requires a server deployment, DNS and owner/admin access before it is accessible publicly. Hostinger's specific hosting plan needs to support persistent Python web applications; many shared plans do not. A Python VPS/PaaS is suitable.

## Production and consent checklist

- Use a unique administrator password and a strong persistent `SESSION_SECRET` stored only as secret environment variables; set `SESSION_SECURE=1` behind HTTPS.
- Configure HTTPS, firewall, proper upload/storage quotas, automatic backups of `data/studio.sqlite3` **and** `data/uploads/`, and restrict application logs.
- This starter uses a single administrator password. Add individual user accounts, sign-in rate limits, and enhanced content moderation before a large editorial team uses it.
- Collect **explicit recording, photo and publication permission** from every speaker, guest and patient; avoid identifying patient details or sensitive case information without an adequate lawful basis.
- Edit machine transcripts for accuracy and obtain editorial/clinical review for health claims, medications and medical advice. Include clear educational disclaimers.
- Keep personal medical information out of raw recordings unless explicit permission, institutional policy and data protection measures are satisfied.
- Server default file limit: 300 MB (`MAX_UPLOAD_MB=300`); reverse proxy will usually need a matching size limit. Consider external object storage/CDN for large/high-traffic archives.

## Files

- `app.py`: FastAPI application, SQLite persistence, authentication, uploads, transcription endpoint.
- `static/index.html`: frontend structure.
- `static/style.css`: responsive branding and styles.
- `static/app.js`: listening library, editor and transcript interactions.
- `requirements.txt`: minimum dependencies.
- `data/`: persistent database/media folder created automatically; **do not check it into a public repository**.

GSHER visual identity: dark teal, soft mint and lime; message: *Self-healthcare is the best healthcare.*
