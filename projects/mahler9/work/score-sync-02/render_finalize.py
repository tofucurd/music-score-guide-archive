"""Isolated candidate: crash-safe, no-overwrite final publication after full QC.
Call recover_verified before validating resumable chunk files. Root lock held.
Intent must be created ONLY after PCM and every video PTS have passed.
"""
from pathlib import Path
import os,json,hashlib

def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  while b:=f.read(4*1024*1024):h.update(b)
 return h.hexdigest()

def sync_directory(path):
 fd=os.open(str(Path(path)),os.O_RDONLY)
 try:os.fsync(fd)
 finally:os.close(fd)

def atomic_json(path,obj):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
 tmp=path.with_suffix(path.suffix+'.tmp')
 with tmp.open('w') as f:
  json.dump(obj,f,ensure_ascii=False,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
 os.replace(tmp,path);sync_directory(path.parent)

def finish_verified(intent_path,run_hash,result_paths,*,cleanup_paths=()):
 """Return False if no verified publication intent; never infer QC from media alone."""
 intent_path=Path(intent_path)
 if not intent_path.exists():return False
 intent=json.loads(intent_path.read_text())
 if intent['run_hash']!=run_hash or intent['qc_complete'] is not True:
  raise ValueError('Finalization intent does not belong to this verified run')
 result=intent['result'];delivery=Path(result['output']);partial=Path(intent['partial'])
 if delivery.exists():
  if delivery.stat().st_size!=result['bytes'] or sha(delivery)!=result['sha256']:
   raise ValueError('Existing delivery differs; preserving it')
 else:
  if not partial.exists():raise ValueError('Verified publication source absent')
  if partial.stat().st_size!=result['bytes'] or sha(partial)!=result['sha256']:
   raise ValueError('Verified publication source differs')
  delivery.parent.mkdir(parents=True,exist_ok=True)
  # Atomic exclusive publication: hard-link fails if destination appeared.
  # Same-filesystem requirement is also required by original rename plan.
  os.link(partial,delivery);sync_directory(delivery.parent)
 for path in result_paths:atomic_json(path,result)
 # Verified final exists and metadata persisted before recoverable cleanup.
 cleaned_dirs=set()
 for p in cleanup_paths:
  p=Path(p)
  if p.exists():p.unlink();cleaned_dirs.add(p.parent)
 if partial.exists() and partial!=delivery:partial.unlink();cleaned_dirs.add(partial.parent)
 for directory in cleaned_dirs:sync_directory(directory)
 return result

def record_intent(intent_path,run_hash,partial,result):
 with Path(partial).open('rb') as f:os.fsync(f.fileno())
 atomic_json(intent_path,{'run_hash':run_hash,'qc_complete':True,'partial':str(Path(partial).resolve()),'result':result})
