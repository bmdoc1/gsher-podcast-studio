"""GSHER Podcast Studio — small self-hosted episode library and editor.

Run: ADMIN_PASSWORD='...' SESSION_SECRET='...' uvicorn app:app --host 0.0.0.0 --port 8000
"""
import hmac
import json
import os
import re
import secrets
import shutil
import sqlite3
import subprocess
import tempfile
import time
import threading
import urllib.request
import urllib.error
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from starlette.middleware.sessions import SessionMiddleware
from starlette.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv('PODCAST_DATA_DIR', str(ROOT / 'data')))
UPLOAD_DIR = DATA_DIR / 'uploads'
DATA_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / 'studio.sqlite3'
MAX_UPLOAD_MB = int(os.getenv('MAX_UPLOAD_MB', '300'))
MEDIA_EXTS = {'.mp3':'audio/mpeg','.m4a':'audio/mp4','.wav':'audio/wav','.ogg':'audio/ogg','.webm':'video/webm','.mp4':'video/mp4','.mov':'video/quicktime'}
IMAGE_EXTS = {'.jpg':'image/jpeg','.jpeg':'image/jpeg','.png':'image/png','.webp':'image/webp'}
TRANSCRIPT_EXTS = {'.txt','.vtt','.srt'}
SESSION_SECRET = os.getenv('SESSION_SECRET') or secrets.token_hex(32)
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', '')
FAILED_LOGINS = {}
LOGIN_LOCK = threading.Lock()
LOGIN_WINDOW_SECONDS = 15 * 60
MAX_LOGIN_FAILURES = 5

app = FastAPI(title='GSHER Podcast Studio', docs_url=None, redoc_url=None)
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET, same_site='lax', https_only=os.getenv('SESSION_SECURE','0')=='1', max_age=60*60*24*7)
app.mount('/static', StaticFiles(directory=str(ROOT/'static')), name='static')


def connect():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def initialize():
    with connect() as db:
        db.execute('''CREATE TABLE IF NOT EXISTS episodes (
          id TEXT PRIMARY KEY, title TEXT NOT NULL, series TEXT DEFAULT 'GSHER Conversations',
          language TEXT DEFAULT 'en', episode_date TEXT, description TEXT DEFAULT '',
          transcript TEXT DEFAULT '', status TEXT DEFAULT 'draft',
          media_name TEXT, media_kind TEXT, cover_name TEXT,
          speakers TEXT DEFAULT '[]', created_at TEXT, updated_at TEXT
        )''')
        db.commit()

initialize()


def now(): return datetime.now(timezone.utc).isoformat()

def require_admin(request: Request):
    if not request.session.get('admin'):
        raise HTTPException(status_code=401, detail='Please sign in to the studio.')
    if request.method not in ('GET','HEAD') and request.headers.get('x-csrf-token') != request.session.get('csrf'):
        raise HTTPException(status_code=403, detail='Security token missing. Please refresh and sign in again.')


def asset_url(name):
    return '/media/' + name if name else None


def display(row):
    d = dict(row)
    d['media_url'] = asset_url(d.pop('media_name'))
    d['cover_url'] = asset_url(d.pop('cover_name'))
    d['speakers'] = json.loads(d['speakers'] or '[]')
    for sp in d['speakers']:
        sp['photo_url'] = asset_url(sp.pop('photo_name', None))
    return d


def row_or_404(db, episode_id):
    row = db.execute('SELECT * FROM episodes WHERE id=?', (episode_id,)).fetchone()
    if row is None:
        raise HTTPException(404,'Episode not found')
    return row


def only_own_media_name(name):
    if not re.fullmatch(r'[a-f0-9]{32}\.[a-z0-9]{2,5}', name):
        raise HTTPException(404,'Invalid media name')
    return name


def safe_delete(name):
    if name and re.fullmatch(r'[a-f0-9]{32}\.[a-z0-9]{2,5}', name):
        (UPLOAD_DIR/name).unlink(missing_ok=True)


async def save_upload(upload: Optional[UploadFile], extensions: dict) -> Optional[str]:
    if not upload or not upload.filename:
        return None
    suffix = Path(upload.filename).suffix.lower()
    if suffix not in extensions:
        raise HTTPException(400, f'Unsupported file type: {suffix}. Allowed: {", ".join(extensions)}')
    name = uuid.uuid4().hex + suffix
    path = UPLOAD_DIR / name
    size = 0
    try:
        with path.open('wb') as out:
            while True:
                chunk = await upload.read(1024*1024)
                if not chunk: break
                size += len(chunk)
                if size > MAX_UPLOAD_MB*1024*1024:
                    raise HTTPException(413, f'File is larger than {MAX_UPLOAD_MB} MB')
                out.write(chunk)
        if size == 0: raise HTTPException(400,'Empty file')
        return name
    except Exception:
        path.unlink(missing_ok=True)
        raise
    finally:
        await upload.close()


def parse_speakers(value: str, existing: list):
    try:
        raw = json.loads(value or '[]')
    except json.JSONDecodeError:
        raise HTTPException(400,'Speakers must be valid JSON.')
    if not isinstance(raw,list) or len(raw)>8:
        raise HTTPException(400,'Maximum eight speakers per episode.')
    result=[]
    old_by_id={p.get('id'):p for p in existing}
    for p in raw:
        if not isinstance(p, dict):
            raise HTTPException(400, 'Each speaker must be a valid object.')
        name=str(p.get('name','')).strip()[:100]
        if not name: continue
        sid=str(p.get('id') or uuid.uuid4().hex)[:64]
        old=old_by_id.get(sid, {})
        result.append({'id':sid,'name':name,'role':str(p.get('role','')).strip()[:140],
                       'photo_name':old.get('photo_name')})
    return result


@app.get('/')
def index():
    return FileResponse(ROOT/'static'/'index.html')

@app.get('/media/{filename}')
def media(request:Request, filename: str):
    filename=only_own_media_name(filename)
    path = UPLOAD_DIR / filename
    if not path.is_file(): raise HTTPException(404,'Media not found')
    # Draft and unpublished media must not leak through direct saved links.
    if not request.session.get('admin'):
        with connect() as db:
            published=db.execute('''SELECT 1 FROM episodes WHERE status='published'
                AND (media_name=? OR cover_name=? OR speakers LIKE ?) LIMIT 1''',
                (filename,filename,'%'+filename+'%')).fetchone()
        if not published: raise HTTPException(404,'Media not found')
    ext=path.suffix
    mime=MEDIA_EXTS.get(ext) or IMAGE_EXTS.get(ext)
    if not mime: raise HTTPException(404,'Unsupported media')
    return FileResponse(path, media_type=mime, headers={'X-Content-Type-Options':'nosniff','Cache-Control':'no-store'})

@app.get('/api/session')
def session(request: Request):
    return {'admin': bool(request.session.get('admin')),
            'csrf':request.session.get('csrf') if request.session.get('admin') else None,
            'transcription_available':_whisper_available() or bool(os.getenv('OPENAI_API_KEY')), 
            'password_configured': bool(ADMIN_PASSWORD),
            'briefing_available':bool(os.getenv('OPENAI_API_KEY'))}

@app.post('/api/login')
async def login(request: Request):
    if not ADMIN_PASSWORD: raise HTTPException(503,'Set ADMIN_PASSWORD on the server before using Studio.')
    client=request.client.host if request.client else 'unknown'
    current=time.monotonic()
    with LOGIN_LOCK:
        # A small bounded in-memory limit suitable for this single-instance service.
        if len(FAILED_LOGINS)>2000:
            FAILED_LOGINS.clear()
        times=[t for t in FAILED_LOGINS.get(client,[]) if current-t<LOGIN_WINDOW_SECONDS]
        FAILED_LOGINS[client]=times
        if len(times)>=MAX_LOGIN_FAILURES:
            raise HTTPException(429,'Too many sign-in attempts. Try again after 15 minutes.')
    payload = await request.json()
    given=str(payload.get('password',''))
    if not hmac.compare_digest(given.encode(),ADMIN_PASSWORD.encode()):
        with LOGIN_LOCK:
            FAILED_LOGINS.setdefault(client,[]).append(current)
        raise HTTPException(401,'Incorrect studio password.')
    with LOGIN_LOCK:
        FAILED_LOGINS.pop(client,None)
    request.session.clear()
    request.session['admin']=True
    request.session['csrf']=secrets.token_urlsafe(24)
    return {'ok':True,'csrf':request.session['csrf']}

@app.post('/api/logout')
def logout(request: Request):
    require_admin(request)
    request.session.clear()
    return {'ok':True}

@app.get('/api/episodes')
def list_episodes(request: Request):
    is_admin=bool(request.session.get('admin'))
    with connect() as db:
        rows = db.execute('SELECT * FROM episodes '+('' if is_admin else "WHERE status='published' ")+'ORDER BY episode_date DESC, created_at DESC').fetchall()
    return {'episodes':[display(row) for row in rows]}

@app.get('/api/episodes/{episode_id}')
def get_episode(request: Request, episode_id:str):
    with connect() as db: row = row_or_404(db, episode_id)
    if row['status']!='published' and not request.session.get('admin'):
        raise HTTPException(404,'Episode not found')
    return display(row)

@app.post('/api/episodes')
async def create_episode(request:Request):
    require_admin(request)
    data=await request.json()
    title=str(data.get('title','')).strip()[:180]
    if not title: raise HTTPException(400,'Episode title is required')
    eid=uuid.uuid4().hex[:16]
    date=str(data.get('episode_date') or now()[:10])[:10]
    language=data.get('language','en')
    if language not in ('en','hi','or'): raise HTTPException(400,'Unsupported language')
    t=now()
    with connect() as db:
        db.execute('''INSERT INTO episodes (id,title,series,language,episode_date,description,transcript,status,media_name,media_kind,cover_name,speakers,created_at,updated_at)
                      VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', (eid,title,str(data.get('series','GSHER Conversations'))[:100],language,date,
                       str(data.get('description',''))[:30000],str(data.get('transcript',''))[:500000],'draft',None,None,None,'[]',t,t))
        db.commit()
        return display(row_or_404(db,eid))

@app.put('/api/episodes/{episode_id}')
async def update_episode(request:Request,episode_id:str):
    require_admin(request)
    data=await request.json()
    with connect() as db:
        row=row_or_404(db,episode_id)
        title=str(data.get('title',row['title'])).strip()[:180]
        if not title: raise HTTPException(400,'Title is required')
        language=data.get('language',row['language'])
        if language not in ('en','hi','or'): raise HTTPException(400,'Unsupported language')
        status=data.get('status',row['status'])
        if status not in ('draft','published'): raise HTTPException(400,'Unknown publication status')
        if status=='published' and not row['media_name']:
            raise HTTPException(400,'Upload an audio or video recording before publishing.')
        old=json.loads(row['speakers'] or '[]')
        speakers=parse_speakers(json.dumps(data.get('speakers',old)),old)
        db.execute('''UPDATE episodes SET title=?,series=?,language=?,episode_date=?,description=?,transcript=?,status=?,speakers=?,updated_at=? WHERE id=?''',
                   (title,str(data.get('series',row['series']))[:100],language,str(data.get('episode_date',row['episode_date']))[:10],
                    str(data.get('description',row['description']))[:30000],str(data.get('transcript',row['transcript']))[:500000],status,json.dumps(speakers),now(),episode_id))
        db.commit()
        return display(row_or_404(db,episode_id))

@app.post('/api/episodes/{episode_id}/upload/{kind}')
async def upload_asset(request:Request,episode_id:str,kind:str,file:UploadFile=File(...),speaker_id:str=Form(default='')):
    require_admin(request)
    if kind not in ('media','cover','speaker','transcript'): raise HTTPException(400,'Unknown asset type')
    with connect() as db:
        row=row_or_404(db,episode_id)
        speakers=json.loads(row['speakers'] or '[]')
        if kind=='transcript':
            if Path(file.filename or '').suffix.lower() not in TRANSCRIPT_EXTS: raise HTTPException(400,'Upload .txt, .srt or .vtt')
            payload=await file.read(2_000_001)
            if len(payload)>2_000_000: raise HTTPException(413,'Transcript must be under 2 MB')
            try: content=payload.decode('utf-8-sig')
            except UnicodeDecodeError: raise HTTPException(400,'Use UTF-8 text for transcripts')
            db.execute('UPDATE episodes SET transcript=?,updated_at=? WHERE id=?',(content,now(),episode_id))
            db.commit()
            return display(row_or_404(db,episode_id))
        if kind=='speaker' and not any(p['id']==speaker_id for p in speakers):
            raise HTTPException(400,'Save speaker first, then upload their photo.')
        ext = MEDIA_EXTS if kind=='media' else IMAGE_EXTS
        filename = await save_upload(file,ext)
        try:
            if kind=='media':
                prev=row['media_name']
                db.execute('UPDATE episodes SET media_name=?,media_kind=?,updated_at=? WHERE id=?',
                           (filename, 'video' if Path(filename).suffix in ('.mp4','.mov','.webm') else 'audio',now(),episode_id))
            elif kind=='cover':
                prev=row['cover_name']
                db.execute('UPDATE episodes SET cover_name=?,updated_at=? WHERE id=?',(filename,now(),episode_id))
            else:
                prev=None
                for p in speakers:
                    if p['id']==speaker_id:
                        prev=p.get('photo_name')
                        p['photo_name']=filename
                db.execute('UPDATE episodes SET speakers=?,updated_at=? WHERE id=?',(json.dumps(speakers),now(),episode_id))
            db.commit()
        except Exception:
            safe_delete(filename)
            raise
        safe_delete(prev)
        return display(row_or_404(db,episode_id))

@app.delete('/api/episodes/{episode_id}')
def delete_episode(request:Request,episode_id:str):
    require_admin(request)
    with connect() as db:
        row=row_or_404(db,episode_id)
        speakers=json.loads(row['speakers'] or '[]')
        db.execute('DELETE FROM episodes WHERE id=?',(episode_id,))
        db.commit()
    for name in [row['media_name'],row['cover_name']]+[p.get('photo_name') for p in speakers]: safe_delete(name)
    return {'ok':True}


def _whisper_available():
    try:
        import faster_whisper # noqa
        return shutil.which('ffmpeg') is not None
    except ImportError:
        return False

def _cloud_transcribe(source: Path):
    """Cloud-based file transcription for CPU-limited hosts; may incur charges."""
    if not shutil.which('ffmpeg'):
        raise HTTPException(503,'FFmpeg is needed for cloud transcription. Use the Docker deployment.')
    # Convert audio/video to a compact 48-kbps MP3. Do not send the original video image.
    with tempfile.TemporaryDirectory() as temp:
        audio = Path(temp) / 'podcast-audio.mp3'
        result = subprocess.run(['ffmpeg','-nostdin','-loglevel','error','-y','-i',str(source),
                  '-vn','-ac','1','-ar','16000','-b:a','48k',str(audio)],
                  capture_output=True,timeout=240,check=False)
        if result.returncode!=0 or not audio.exists():
            raise HTTPException(422,'Could not extract audio from the recording.')
        if audio.stat().st_size > 24 * 1024 * 1024:
            raise HTTPException(413,'Recording is too long for a single API transcription. Divide it into shorter parts or import an SRT/TXT transcript.')
        try:
            from openai import OpenAI
            client = OpenAI(api_key=os.environ['OPENAI_API_KEY'], timeout=180.0)
            with audio.open('rb') as handle:
                result=client.audio.transcriptions.create(file=handle,model=os.getenv('TRANSCRIBE_MODEL','gpt-transcribe'))
            transcript=getattr(result,'text','')
            if not transcript or not transcript.strip():
                raise HTTPException(502,'Transcription returned no text.')
            return transcript.strip()[:500000], 'detected automatically', 'cloud'
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(502,'Cloud transcription failed. Check your API key, quota and recording format.')


@app.post('/api/episodes/{episode_id}/transcribe')
def transcribe(request:Request,episode_id:str):
    require_admin(request)
    key=os.getenv('OPENAI_API_KEY','')
    if not key and not _whisper_available():
        raise HTTPException(503,'Configure OPENAI_API_KEY for cloud transcription, or install local faster-whisper and ffmpeg.')
    with connect() as db:
        row=row_or_404(db,episode_id)
        if not row['media_name']: raise HTTPException(400,'Upload a recording first.')
        source=UPLOAD_DIR/row['media_name']
        if key:
            transcript, language, engine = _cloud_transcribe(source)
        else:
            from faster_whisper import WhisperModel
            model=WhisperModel(os.getenv('WHISPER_MODEL','small'),device='cpu',compute_type='int8')
            segments, info=model.transcribe(str(source),beam_size=3,vad_filter=True)
            lines=[]
            for s in segments:
                t=int(s.start)
                lines.append(f'[{t//3600:02d}:{(t//60)%60:02d}:{t%60:02d}] {s.text.strip()}')
            transcript='\n'.join(lines)[:500000]
            language=info.language
            engine='local'
        db.execute('UPDATE episodes SET transcript=?,updated_at=? WHERE id=?',(transcript,now(),episode_id))
        db.commit()
    return {'transcript':transcript,'language_detected':language,'engine':engine,
            'warning':'Machine transcription needs human review, especially for Odia, names, clinical terms and medical advice. Cloud transcription sends extracted audio to the API provider.'}

@app.post('/api/episodes/{episode_id}/brief')
def make_brief(request:Request, episode_id:str):
    """Generate an unverified draft summary; editor must explicitly save it."""
    require_admin(request)
    key=os.getenv('OPENAI_API_KEY', '')
    if not key: raise HTTPException(503,'AI briefing requires OPENAI_API_KEY on the server; otherwise write the brief manually.')
    with connect() as db:
        row=row_or_404(db,episode_id)
    if not row['transcript'].strip(): raise HTTPException(400,'Add or generate a transcript first.')
    lang={'en':'simple English','hi':'simple Hindi','or':'simple Odia'}.get(row['language'],'simple English')
    payload={'model':os.getenv('BRIEF_MODEL','gpt-4o-mini'),'temperature':0.2,
             'messages':[{'role':'system','content':
                'You are a careful public-health education editor for GSHER. Produce a concise episode briefing in '+lang+'. '
                'Use only information supported by the supplied transcript. Start with a 2-3 sentence episode overview, '
                'then 3-5 takeaways and an optional discussion question. Use plain language. Never add new clinical '
                'claims, medication changes, guaranteed cures, personal health advice, or invented quotes. If a claim '
                'is uncertain or controversial, describe it as something the speaker said, not established fact. '
                'Do not include private patient identifiers. Finish: Educational only; consult your clinician for personal care.'},
                 {'role':'user','content':'Episode: '+row['title']+'\nTranscript:\n'+row['transcript'][:26000]}],
             'max_tokens':900}
    body=json.dumps(payload).encode('utf-8')
    req=urllib.request.Request('https://api.openai.com/v1/chat/completions',data=body,
       headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'},method='POST')
    try:
        with urllib.request.urlopen(req, timeout=100) as reply:
            data=json.load(reply)
        brief=data['choices'][0]['message']['content']
        if not isinstance(brief,str) or not brief.strip():
            raise ValueError('Empty briefing')
    except (urllib.error.URLError, KeyError, ValueError, IndexError) as exc:
        raise HTTPException(502,'AI briefing service unavailable: '+str(exc)[:200])
    return {'brief':brief.strip(),'warning':'AI-generated draft: verify transcript, clinical accuracy, names and permission before saving or publishing.'}

@app.get('/health')
def health(): return {'ok':True}
