import test from 'node:test';
import assert from 'node:assert/strict';
import worker from '../public/_worker.js';

function environment() {
  const episodes=new Map(), attempts=new Map(), uploads=new Map(), objects=new Map(), multipart=new Map();
  const DB={prepare(query){let args=[];return {bind(...a){args=a;return this},async first(){
    if(query.includes('FROM login_attempts'))return attempts.get(args[0])||null;
    if(query.includes('FROM upload_sessions'))return uploads.get(args[0])||null;
    if(query.includes('SELECT id FROM episodes WHERE status='))return [...episodes.values()].find(e=>e.status==='published'&&(e.media_name===args[0]||e.cover_name===args[1]||e.speakers.includes(args[2].replaceAll('%',''))))||null;
    if(query.includes('FROM episodes WHERE id='))return episodes.get(args[0])||null;
    throw Error('Unsupported test D1 first: '+query);
  },async all(){if(query.includes('FROM episodes'))return {results:[...episodes.values()].filter(x=>query.includes("status='published'")?x.status==='published':true)};throw Error('Unsupported D1 all: '+query);},async run(){
    if(query.startsWith('INSERT INTO episodes')){const [id,title,series,language,episode_date,description,transcript,status,speakers,created_at,updated_at]=args;episodes.set(id,{id,title,series,language,episode_date,description,transcript,status,speakers,created_at,updated_at,media_name:null,media_kind:null,cover_name:null});}
    else if(query.startsWith('UPDATE episodes SET media_name=')){const [media_name,media_kind,updated_at,id]=args;Object.assign(episodes.get(id),{media_name,media_kind,updated_at});}
    else if(query.startsWith('UPDATE episodes SET cover_name=')){const [cover_name,updated_at,id]=args;Object.assign(episodes.get(id),{cover_name,updated_at});}
    else if(query.startsWith('UPDATE episodes SET speakers=')){const [speakers,updated_at,id]=args;Object.assign(episodes.get(id),{speakers,updated_at});}
    else if(query.startsWith('UPDATE episodes SET transcript=')){const [transcript,updated_at,id]=args;Object.assign(episodes.get(id),{transcript,updated_at});}
    else if(query.startsWith('UPDATE episodes SET title=')){const [title,series,language,episode_date,description,transcript,status,speakers,updated_at,id]=args;Object.assign(episodes.get(id),{title,series,language,episode_date,description,transcript,status,speakers,updated_at});}
    else if(query.startsWith('DELETE FROM episodes'))episodes.delete(args[0]);
    else if(query.startsWith('INSERT INTO login_attempts'))attempts.set(args[0],{count:args[1],first_at:args[2]});
    else if(query.startsWith('DELETE FROM login_attempts'))attempts.delete(args[0]);
    else if(query.startsWith('INSERT INTO upload_sessions')){const [id,episode_id,r2_key,r2_upload_id,size_bytes,created_at]=args;uploads.set(id,{id,episode_id,r2_key,r2_upload_id,size_bytes,created_at});}
    else if(query.startsWith('DELETE FROM upload_sessions'))uploads.delete(args[0]);
    else throw Error('Unsupported test D1 run: '+query);
  }}}};
  const MEDIA={
    async get(key){const data=objects.get(key);return data?{body:new Blob([data]).stream(),size:data.length,range:null}:null;},
    async put(key,body){objects.set(key,Buffer.from(await new Response(body).arrayBuffer()));return {key}},
    async delete(key){for(const k of (Array.isArray(key)?key:[key]))objects.delete(k)},
    createMultipartUpload(key){const uploadId='mock-'+crypto.randomUUID(),parts=new Map();multipart.set(uploadId,{key,parts});return {uploadId,key}},
    resumeMultipartUpload(key,uploadId){const mp=multipart.get(uploadId);if(!mp||mp.key!==key)throw Error('Multipart session unknown');return {
      async uploadPart(n,body){mp.parts.set(n,Buffer.from(await new Response(body).arrayBuffer()));return {partNumber:n,etag:'etag-'+n}},
      async complete(all){objects.set(key,Buffer.concat(all.map(p=>mp.parts.get(p.partNumber))));multipart.delete(uploadId);return {key}},
      async abort(){multipart.delete(uploadId)}
    }}
  };
  return {DB,MEDIA,ASSETS:{fetch:async()=>new Response('UI available')},ADMIN_PASSWORD:'secure-test-password',SESSION_SECRET:'some-very-long-test-secret-do-not-reuse'};
}
async function send(env,path,{method='GET',body,headers={}}={}){const init={method,headers};if(body!==undefined)init.body=body;return worker.fetch(new Request('https://podcast.example.test'+path,init),env);}
test('unauthenticated writes are blocked; health and session work',async()=>{const env=environment();assert.equal((await send(env,'/health')).status,200);assert.equal((await send(env,'/api/session').then(x=>x.json())).admin,false);const deny=await send(env,'/api/episodes',{method:'POST',body:JSON.stringify({title:'Untrusted'})});assert.equal(deny.status,401)});
test('login and draft-to-public privacy transition',async()=>{
 const env=environment();const login=await send(env,'/api/login',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({password:'secure-test-password'})});assert.equal(login.status,200);const cookie=login.headers.get('set-cookie').split(';')[0],{csrf}=await login.json(),auth={'cookie':cookie,'x-csrf-token':csrf};
 let created=await send(env,'/api/episodes',{method:'POST',headers:auth,body:JSON.stringify({title:'CelluReva talk'})});assert.equal(created.status,201);const {id}=await created.json();
 let publicList=await (await send(env,'/api/episodes')).json();assert.equal(publicList.episodes.length,0);
 const fd=new FormData();fd.append('file',new File([new Uint8Array([3,4,5])],'talk.mp3',{type:'audio/mpeg'}));let uploaded=await send(env,`/api/episodes/${id}/upload/media`,{method:'POST',headers:auth,body:fd});assert.equal(uploaded.status,200);const mediaUrl=(await uploaded.json()).media_url;
 assert.equal((await send(env,mediaUrl)).status,404);
 const row=await (await send(env,`/api/episodes/${id}`,{headers:auth})).json();const update={...row,status:'published'};
 assert.equal((await send(env,`/api/episodes/${id}`,{method:'PUT',headers:auth,body:JSON.stringify(update)})).status,200);
 assert.equal((await send(env,mediaUrl)).status,200);
 assert.equal((await (await send(env,'/api/episodes')).json()).episodes.length,1);
 update.status='draft';assert.equal((await send(env,`/api/episodes/${id}`,{method:'PUT',headers:auth,body:JSON.stringify(update)})).status,200);
 assert.equal((await send(env,mediaUrl)).status,404);
 const badCsrf=await send(env,`/api/episodes/${id}`,{method:'DELETE',headers:{cookie},body:''});assert.equal(badCsrf.status,403);
 assert.equal((await send(env,`/api/episodes/${id}`,{method:'DELETE',headers:auth})).status,200);
});
test('incorrect password is rejected',async()=>{const env=environment();let x=await send(env,'/api/login',{method:'POST',body:JSON.stringify({password:'wrong'})});assert.equal(x.status,401)});

test('large audio recording uses chunked R2 multipart upload',async()=>{
 const env=environment();const login=await send(env,'/api/login',{method:'POST',body:JSON.stringify({password:'secure-test-password'})});
 const cookie=login.headers.get('set-cookie').split(';')[0],{csrf}=await login.json(),headers={cookie,'x-csrf-token':csrf};
 const ep=await (await send(env,'/api/episodes',{method:'POST',headers,body:JSON.stringify({title:'Long conversation'})})).json();
 const size=9*1024*1024;
 const start=await send(env,`/api/episodes/${ep.id}/uploads`,{method:'POST',headers,body:JSON.stringify({filename:'interview.mp3',size})});
 assert.equal(start.status,201);const session=await start.json();assert.equal(session.part_size,8*1024*1024);
 const parts=[];for(const [n,bytes] of [[1,8*1024*1024],[2,1*1024*1024]]){
   const res=await send(env,`/api/episodes/${ep.id}/uploads/${session.id}/parts/${n}`,{method:'PUT',headers:{...headers,'content-length':String(bytes)},body:new Uint8Array(bytes)});
   assert.equal(res.status,200);parts.push(await res.json());
 }
 const done=await send(env,`/api/episodes/${ep.id}/uploads/${session.id}/complete`,{method:'POST',headers,body:JSON.stringify({parts})});
 assert.equal(done.status,200);assert.ok((await done.json()).media_url.endsWith('.mp3'));
});


test('public Pages assets remain available before D1/R2 setup',async()=>{
 const env={ASSETS:{fetch:async()=>new Response('PUBLIC PAGE',{status:200})}};
 const page=await worker.fetch(new Request('https://test.pages.dev/'),env);
 assert.equal(page.status,200);assert.equal(await page.text(),'PUBLIC PAGE');
 const api=await worker.fetch(new Request('https://test.pages.dev/api/episodes'),env);
 assert.equal(api.status,503);
});
