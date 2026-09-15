from __future__ import annotations
import argparse, hashlib, json, mimetypes, os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv

ROOT=Path(__file__).resolve().parents[2]; DATA=ROOT/'backend'/'data'; load_dotenv(ROOT/'backend'/'.env')
@dataclass(frozen=True)
class SourceData:
    users:list; plans:list; owners:dict; conversations:list; memories:dict; subscriptions:dict; payments:dict; usage:dict
def _load(n): return json.loads((DATA/n).read_text(encoding='utf-8'))
def load_and_validate_source_data():
    users=_load('users.json')['users']; plans=_load('plans.json')['plans']; owners=_load('document_owners.json').get('owners',{}); conv=_load('conversations.json')['conversations']; mem=_load('core_memory.json'); subs=_load('subscriptions.json').get('subscriptions',{}); pays=_load('payments.json').get('payments',{}); usage=_load('usage.json').get('days',{})
    uids={u['id'] for u in users}; pids={p['id'] for p in plans}
    if len(uids)!=len(users) or len(pids)!=len(plans): raise ValueError('Identifiants source dupliqués')
    if any(x.get('user_id') not in uids for x in conv): raise ValueError('Conversation sans utilisateur')
    if any(uid not in uids or s.get('plan_id') not in pids for uid,s in subs.items()): raise ValueError('Subscription invalide')
    if any(p.get('user_id') not in uids or p.get('plan_id') not in pids for p in pays.values()): raise ValueError('Payment invalide')
    return SourceData(users,plans,owners,conv,mem,subs,pays,usage)
def import_json_to_postgres(connection, d):
    print('START plans', flush=True)
    for p in d.plans: connection.execute('INSERT INTO plans VALUES(%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(id) DO NOTHING',(p['id'],p['name'],p['monthly_price'],p['annual_price'],p['documents'],p['daily_requests'],json.dumps(p.get('features',[]))))
    print('OK plans', flush=True); print('START users', flush=True)
    for u in d.users: connection.execute('INSERT INTO users(id,phone,name,password_hash,onboarding_completed,level,subjects,goal,learning_style,difficulties,welcome_seen,created_at) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(id) DO NOTHING',(u['id'],u['phone'],u.get('name','Etudiant'),u['password_hash'],u.get('onboarding_completed',False),u.get('level'),json.dumps(u.get('subjects',[])),u.get('goal'),u.get('learning_style'),u.get('difficulties'),u.get('welcome_seen',False),u.get('created_at',datetime.now(timezone.utc))))
    print('OK users', flush=True); print('START documents', flush=True)
    for name,uid in d.owners.items():
        f=DATA/'uploads'/name
        if f.exists():
            stamp=datetime.fromtimestamp(f.stat().st_mtime,timezone.utc); connection.execute('INSERT INTO documents VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(id) DO NOTHING',(hashlib.sha256(name.encode()).hexdigest()[:16],uid,name,str(f),mimetypes.guess_type(name)[0] or 'application/octet-stream',f.stat().st_size,hashlib.sha256(f.read_bytes()).hexdigest(),'ready',stamp,stamp))
    print('OK documents', flush=True); print('START conversations', flush=True)
    for x in d.conversations:
        connection.execute('INSERT INTO conversations VALUES(%s,%s,%s,%s,%s) ON CONFLICT(id) DO NOTHING',(x['id'],x['user_id'],x['title'],x.get('created_at',datetime.now(timezone.utc)),x['updated_at']))
        for i,m in enumerate(x.get('messages',[])): connection.execute('INSERT INTO messages VALUES(md5(%s)::uuid,%s,%s,%s,%s) ON CONFLICT DO NOTHING',(f"{x['id']}:{i}",x['id'],m['role'],m['content'],x['updated_at']))
    print('OK conversations', flush=True); print('START messages', flush=True)
    print('OK messages', flush=True); print('START memories', flush=True)
    for uid,v in d.memories.items():
        for k,val in v.items(): connection.execute("INSERT INTO memories VALUES(md5(%s)::uuid,%s,'fact',%s,%s,now(),now()) ON CONFLICT(user_id,memory_key) DO UPDATE SET content=EXCLUDED.content",(uid+':'+k,uid,k,str(val)))
    print('OK memories', flush=True); print('START subscriptions', flush=True)
    for uid,s in d.subscriptions.items(): connection.execute('INSERT INTO subscriptions VALUES(md5(%s)::uuid,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING',(uid,uid,s.get('plan_id'),s.get('status'),s.get('billing_cycle'),s.get('started_at'),s.get('expires_at'),s.get('last_transaction_id')))
    print('OK subscriptions', flush=True); print('START payments', flush=True)
    for tid,p in d.payments.items(): connection.execute('INSERT INTO payments VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING',(tid,p.get('user_id'),p.get('plan_id'),p.get('billing_cycle'),p.get('amount',0),p.get('currency','USD'),p.get('status','unknown'),p.get('simulation',False),p.get('created_at')))
    print('OK payments', flush=True); print('START daily_usage', flush=True)
    for day,v in d.usage.items():
        for uid,n in v.items(): connection.execute('INSERT INTO daily_usage VALUES(%s,%s,%s) ON CONFLICT (user_id, usage_date) DO UPDATE SET ai_requests=EXCLUDED.ai_requests',(uid,day,n))
    print('OK daily_usage', flush=True)
def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--dry-run',action='store_true'); args=parser.parse_args(); d=load_and_validate_source_data(); print('source_validated',len(d.users),len(d.plans),len(d.conversations), flush=True)
    if args.dry_run: print('dry_run=True'); return
    import psycopg
    url=os.environ.get('DATABASE_URL','').strip()
    if not url: raise RuntimeError('DATABASE_URL manquante')
    migration=(Path(__file__).resolve().parents[1]/'migrations'/'001_initial.sql').read_text(encoding='utf-8')
    with psycopg.connect(url) as connection:
        with connection.cursor() as cursor: cursor.execute(migration)
        import_json_to_postgres(connection, d)
        connection.commit()
    print('migration_complete=True', flush=True)
if __name__=='__main__': main()
