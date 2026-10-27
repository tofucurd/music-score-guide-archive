"""Source-native ownership. Display staff and storage staff are distinct."""
import xml.etree.ElementTree as X
NS='{http://www.music-encoding.org/ns/mei}'
ID='{http://www.w3.org/XML/1998/namespace}id'
from beamspan_members import resolve_beamspans

def mei_index(source):
 root=X.fromstring(source);records={}
 def visit(e,storage=None,raw=None):
  tag=e.tag.split('}')[-1]
  if tag=='staff':storage=e.get('n')
  explicit=e.get('staff','').split();key=e.get(ID)
  if key:
   records[key]=dict(tag=tag,storage_staff=storage,staffs=explicit or ([storage] if storage else []),
    start=e.get('startid','').lstrip('#') or None,end=e.get('endid','').lstrip('#') or None,
    refs=[p.lstrip('#') for p in e.get('plist','').split()],
    notes=[n.get(ID) for n in e.iter(NS+'note') if n.get(ID)] if tag in ['beam','beamSpan','chord','tuplet'] else [],
    tstamp=e.get('tstamp'),tstamp2=e.get('tstamp2'))
  for c in e:visit(c,storage,raw)
 visit(root)
 for key,span in resolve_beamspans(source).items():
  records[key]['notes']=span['member_ids']
 def resolve(key,seen=None):
  seen=set() if seen is None else seen
  if key in seen or key not in records:return []
  seen.add(key);r=records[key];values=set(r['staffs'])
  for ref in [r['start'],r['end'],*r['refs'],*r['notes']]:
   if ref:values.update(resolve(ref,seen))
  return sorted(values,key=int)
 for key,r in records.items():r['staffs']=resolve(key)
 return records
