"""Resolve native MEI beamSpan members, preserving storage voice across measures.
No shared renderer mutation. Import resolve_beamspans(mei_bytes) in scene_source.
"""
import xml.etree.ElementTree as ET
from collections import defaultdict
NS='{http://www.music-encoding.org/ns/mei}';ID='{http://www.w3.org/XML/1998/namespace}id'
def resolve_beamspans(mei_bytes):
 root=ET.fromstring(mei_bytes);parent={c:p for p in root.iter() for c in p};index={e.get(ID):e for e in root.iter() if e.get(ID)};measure_order={e:i+1 for i,e in enumerate(root.iter(NS+'measure'))};lanes=defaultdict(list);position={};metadata={}
 def ancestor(e,tag):
  while e in parent:
   e=parent[e]
   if e.tag==NS+tag:return e
  return None
 # A layer's xml:id changes each measure. Stable stream is storage staff@n + layer@n.
 for measure,raw in measure_order.items():
  for staff in measure.findall(NS+'staff'):
   for layer in staff.findall(NS+'layer'):
    lane=(staff.get('n'),layer.get('n','1'))
    for e in layer.iter():
     if e.tag not in [NS+'note',NS+'chord',NS+'rest',NS+'space']:continue
     key=e.get(ID)
     if not key:continue
     # Chord is a single ordered stream event. Notes inside it share its index.
     chord=ancestor(e,'chord') if e.tag==NS+'note' else None
     owner=chord if chord is not None else e;ownerkey=owner.get(ID)
     if ownerkey not in position:
      position[ownerkey]=(lane,len(lanes[lane]));lanes[lane].append(ownerkey)
     position[key]=position[ownerkey]
     display=e.get('staff') or owner.get('staff') or staff.get('n')
     metadata[key]={'storage_staff':staff.get('n'),'display_staff':display,'layer_n':layer.get('n','1'),'raw_measure':raw,'tag':e.tag.split('}')[-1],'stem_direction':e.get('stem.dir') or owner.get('stem.dir')}
 def note_ids(key):
  e=index[key]
  return [key] if e.tag==NS+'note' else [n.get(ID) for n in e.iter(NS+'note') if n.get(ID)]
 spans={}
 for span in root.iter(NS+'beamSpan'):
  key=span.get(ID);start=span.get('startid','').lstrip('#');end=span.get('endid','').lstrip('#');plist=[x.lstrip('#') for x in span.get('plist','').split()]
  if start not in position or end not in position:raise ValueError(f'{key}: unresolved endpoints {start} {end}')
  (lane,a),(end_lane,b)=position[start],position[end]
  if lane!=end_lane:raise ValueError(f'{key}: endpoints in different STORAGE voice streams; explicit graph required')
  if b<a:raise ValueError(f'{key}: reversed stream endpoints')
  candidates=lanes[lane][a:b+1]
  if plist:
   missing=set(plist)-index.keys()
   if missing:raise ValueError(f'{key}: unknown plist {missing}')
   # plist is authoritative membership, endpoints remain mandatory.
   candidates=list(dict.fromkeys([start,*plist,end]))
  members=list(dict.fromkeys(n for k in candidates for n in note_ids(k)))
  if not members:raise ValueError(f'{key}: empty member graph')
  spans[key]={'id':key,'start':start,'end':end,'storage_staff':lane[0],'layer_n':lane[1],'member_ids':members,'member_metadata':{n:metadata[n] for n in members},'raw_measure_range':[min(metadata[n]['raw_measure'] for n in members),max(metadata[n]['raw_measure'] for n in members)],'display_staffs':sorted({metadata[n]['display_staff'] for n in members},key=int),'resolution':'explicit_plist' if plist else 'inclusive_same_storage_staff_layer_source_order','contains_rests':any(index[k].tag in [NS+'rest',NS+'space'] for k in candidates)}
 return spans
if __name__=='__main__':
 import json,pathlib
 meta=json.load(open('work/score-sync-02/canonical/M1/source.json'));spans=resolve_beamspans(pathlib.Path(meta['normalized_mei']['path']).read_bytes());out=pathlib.Path('work/score-sync-02/team/a/beamspan-members-M1.json');out.write_text(json.dumps(spans,ensure_ascii=False,indent=2));print({k:(len(v['member_ids']),v['raw_measure_range'],v['display_staffs']) for k,v in spans.items()})
