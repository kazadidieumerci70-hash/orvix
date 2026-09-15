import json
from .config import get_settings
from .json_store import atomic_write_json

def _path(): return get_settings().data_dir / "core_memory.json"
def _read():
    p=_path(); return json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}
def remember(user_id: str, message: str) -> None:
    import re
    m=re.search(r"je m'appelle\s+([A-Za-zÀ-ÿ-]+)", message, re.I)
    if m:
        data=_read(); data.setdefault(user_id,{})['prenom']=m.group(1); atomic_write_json(_path(),data)
def relevant(user_id: str, message: str) -> str:
    data=_read().get(user_id,{})
    if any(x in message.casefold() for x in ('comment je m’appelle','comment je m\'appelle','quel est mon prénom','quel est mon prenom')) and data.get('prenom'):
        return f"Mémoire pertinente : le prénom de l’utilisateur est {data['prenom']}."
    return ''
