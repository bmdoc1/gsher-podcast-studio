"""Smoke tests for login, drafting, consented upload, publication and draft-media privacy."""
import importlib
import io
import os
from fastapi.testclient import TestClient


def test_editor_to_public_library(tmp_path, monkeypatch):
    monkeypatch.setenv('PODCAST_DATA_DIR', str(tmp_path / 'data'))
    monkeypatch.setenv('ADMIN_PASSWORD', 'unique-password-for-this-local-test-only')
    monkeypatch.setenv('SESSION_SECRET', 'test-secret-for-signed-session-cookies-not-production')
    monkeypatch.setenv('SESSION_SECURE', '0')
    import app
    importlib.reload(app)
    a = TestClient(app.app)
    b = TestClient(app.app)
    assert a.get('/health').json()['ok'] is True
    assert not a.get('/api/session').json()['admin']
    assert a.post('/api/episodes', json={'title':'Unsigned request'}).status_code == 401
    assert a.post('/api/login',json={'password':'wrong'}).status_code == 401
    r=a.post('/api/login',json={'password':'unique-password-for-this-local-test-only'})
    assert r.status_code == 200
    csrf=r.json()['csrf']
    h={'x-csrf-token':csrf}
    assert a.post('/api/episodes',json={'title':'No CSRF'}).status_code == 403
    cr=a.post('/api/episodes',headers=h,json={'title':'Test conversation','language':'or'})
    assert cr.status_code == 200, cr.text
    eid=cr.json()['id']
    assert b.get('/api/episodes').json()['episodes']==[]
    up=a.post(f'/api/episodes/{eid}/upload/media',headers=h,files={'file':('voice.mp3',io.BytesIO(b'ID3short-test-content'),'audio/mpeg')})
    assert up.status_code==200,up.text
    media_path=up.json()['media_url']
    assert b.get(media_path).status_code==404, 'Unpublished audio must remain inaccessible'
    assert a.get(media_path).status_code==200
    pub=a.put(f'/api/episodes/{eid}',headers=h,json={'status':'published','title':'Test conversation','language':'or'})
    assert pub.status_code==200,pub.text
    assert len(b.get('/api/episodes').json()['episodes'])==1
    assert b.get(media_path).status_code==200
    draft=a.put(f'/api/episodes/{eid}',headers=h,json={'status':'draft','title':'Test conversation'})
    assert draft.status_code==200,draft.text
    assert b.get(media_path).status_code==404, 'Switching back to draft must revoke public access'
    assert a.delete(f'/api/episodes/{eid}',headers=h).status_code==200
    assert b.get(media_path).status_code==404


def test_transcription_audio_extraction_no_external_api(tmp_path, monkeypatch):
    """Verify the configured cloud path compresses a video/audio file first and handles the API response."""
    import wave
    import sys
    import types
    from pathlib import Path
    monkeypatch.setenv('OPENAI_API_KEY','fake-test-key-do-not-use')
    import app
    source=tmp_path/'tiny.wav'
    with wave.open(str(source),'wb') as out:
        out.setnchannels(1);out.setsampwidth(2);out.setframerate(16000)
        out.writeframes(b'\x00\x00'*16000)
    captured=[]
    class DummyTranscriptions:
        def create(self, file, model):
            captured.append((file.name,model,Path(file.name).stat().st_size))
            return types.SimpleNamespace(text='Testing GSHER audio transcription.')
    class DummyOpenAI:
        def __init__(self,**kwargs):
            assert kwargs['api_key']=='fake-test-key-do-not-use'
            self.audio=types.SimpleNamespace(transcriptions=DummyTranscriptions())
    monkeypatch.setitem(sys.modules,'openai',types.SimpleNamespace(OpenAI=DummyOpenAI))
    text, language, engine=app._cloud_transcribe(source)
    assert text=='Testing GSHER audio transcription.'
    assert engine=='cloud'
    assert captured[0][1]=='gpt-transcribe'
    assert captured[0][2]>0
