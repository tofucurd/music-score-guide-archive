"""Reproducible source identity, sounding cohort and native-asset gate."""
from pathlib import Path
import json,hashlib,math
from frame_params import Frames,NEW,OLD
load=lambda p:json.loads(Path(p).read_text())
def main():
 r=Frames();report={'all_92_sections_present':False,'failures':[],'movements':[]}
 for m in range(1,5):
  d,g,meta,curve,bounds,sched=r.actor(m);ids={n['id'] for n in d['notes']}; native={n['engraver_id'] for n in d['notes'] if n['visible']};missing=native-set(g['note_boxes'])
  failures=[]
  if missing:failures.append({'missing_native_heads':sorted(missing)})
  if meta['unknown'] or g['unknown']:failures.append({'unknown_source_owners':meta['unknown'],'unknown_geometry':g['unknown']})
  sections=d['sections'];expected=0;checks=0
  for section in sections:
   a,b=section['range'];required=set(section['requested_staves'])
   if a!=expected or b<=a:failures.append({'section_range':section['id']})
   expected=b
   sounding=set()
   for n in d['notes']:
    if n['range'][0]<b and r.ends[m][n['id']]>a:sounding.update((n['staff'],n['storage_staff']))
   if sounding-required:failures.append({'section':section['id'],'missing_sounding_rows':sorted(sounding-required,key=int)})
   for t in [a/96000,(a+b)/192000,(b-1)/96000]:
    layout=sched.layout(t);checks+=1
    if any(layout['weights'].get(st,0)!=1 for st in required):failures.append({'section':section['id'],'not_opaque_at':t})
    if not math.isfinite(layout['scale']) or layout['scale']<=0:failures.append({'invalid_scale_at':t})
  own=r.timeline['movements'][m-1]
  if expected!=own['global_range'][1]-own['global_range'][0]:failures.append({'noncontinuous_movement_range':expected})
  report['movements'].append(dict(movement=m,source_notes=len(ids),visible_native_heads=len(native),source_sections=len(sections),layout_checks=checks,source_ties=sum(c['tag']=='tie' for c in meta['controls'].values()),colored_tie_extended_notes=len(r.colors[m]),failures=failures))
  report['failures'] += [dict(movement=m,detail=f) for f in failures]
  print('M',m,'sections',len(sections),'failures',len(failures),flush=True)
 for key in r.materials:
  movement,nid=key.split('/',1);m=int(movement[1:]);notes=r.actor(m)[0]['notes']
  if nid not in {n['id'] for n in notes}:report['failures'].append({'unknown_material_id':key})
 report['all_92_sections_present']=sum(x['source_sections'] for x in report['movements'])==92
 report['source_note_count']=sum(x['source_notes'] for x in report['movements'])
 report['scope']='Every source note/native mapping and each complete sounding section including explicit tie continuation; three layout samples per section. This does not replace all-frame connector/label or actual encoded visual review.'
 (NEW/'asset-audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
 assert report['all_92_sections_present'] and not report['failures'],report['failures'][:10]
if __name__=='__main__':main()
