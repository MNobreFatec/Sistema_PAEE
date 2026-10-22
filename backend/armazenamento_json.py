"""Armazenamento persistente em JSON para desenvolvimento local sem PostgreSQL.
Não contém registros de exemplo: o arquivo nasce vazio e recebe apenas dados enviados.
"""
import json
import os
import threading
from pathlib import Path
from datetime import datetime, date

DATA_FILE = Path(os.getenv('PAEE_JSON_FILE', Path(__file__).resolve().parent / 'data' / 'paee.json'))
_LOCK = threading.RLock()
COLLECTIONS = ('usuarios','solicitacoes','formularios','designacoes','relatorios','feedbacks','assinaturas')

def _empty():
    return {**{name: [] for name in COLLECTIONS}, 'counters': {name: 0 for name in COLLECTIONS}}

def _read():
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not DATA_FILE.exists():
        DATA_FILE.write_text(json.dumps(_empty(), ensure_ascii=False, indent=2), encoding='utf-8')
    try:
        data = json.loads(DATA_FILE.read_text(encoding='utf-8'))
    except (json.JSONDecodeError, OSError) as exc:
        raise RuntimeError(f'Não foi possível ler {DATA_FILE}: {exc}')
    base = _empty()
    base.update(data)
    for key in COLLECTIONS: base.setdefault(key, [])
    base.setdefault('counters', {})
    return base

def _write(data):
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = DATA_FILE.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
    tmp.replace(DATA_FILE)

def all_rows(collection):
    with _LOCK: return _read()[collection]

def get(collection, field, value):
    with _LOCK:
        return next((r for r in _read()[collection] if str(r.get(field)) == str(value)), None)

def create(collection, row, id_field):
    with _LOCK:
        data = _read()
        created = append_record(data, collection, row, id_field)
        _write(data)
        return created

def append_record(data, collection, row, id_field):
    if collection not in COLLECTIONS:
        raise ValueError(f'Coleção desconhecida: {collection}')
    data['counters'][collection] = max(
        int(data['counters'].get(collection, 0)),
        max((int(record.get(id_field, 0)) for record in data[collection]), default=0),
    ) + 1
    created = dict(row)
    created[id_field] = data['counters'][collection]
    data[collection].append(created)
    return created

def create_many(records):
    with _LOCK:
        data = _read()
        created = []
        for collection, row, id_field in records:
            row = row(created) if callable(row) else row
            created.append(append_record(data, collection, row, id_field))
        _write(data)
        return created

def update(collection, id_field, ident, changes):
    with _LOCK:
        data = _read()
        for row in data[collection]:
            if str(row.get(id_field)) == str(ident):
                row.update(changes); _write(data); return row
        return None

def mutate(fn):
    with _LOCK:
        data = _read(); result = fn(data); _write(data); return result

def health():
    return {'storage':'json','file':str(DATA_FILE),'records':{k:len(v) for k,v in _read().items() if isinstance(v,list)}}
