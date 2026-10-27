"""Freeze one native engraving per movement, then virtualize its measures.

No musical object is re-engraved when the displayed staff cohort changes.
"""
from pathlib import Path
import sys,json,hashlib,xml.etree.ElementTree as X,re,argparse,time,ast
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];OLD=ROOT/'work/score-sync-01'
sys.path.insert(0,str(OLD))
from prepare_data import L,load,dump,ref
from trill_display import repair,repair_svg
sys.path.insert(0,str(L))
from native_staff_projection import project_stable_staves
from scene_source import mei_index
import verovio
SVG='http://www.w3.org/2000/svg';S='{'+SVG+'}';N='{http://www.music-encoding.org/ns/mei}';ID='{http://www.w3.org/XML/1998/namespace}id';XL='{http://www.w3.org/1999/xlink}href'
X.register_namespace('',SVG);X.register_namespace('xlink','http://www.w3.org/1999/xlink')

def text(e):return ''.join(e.itertext()).strip()
def build(m):
 out=HERE/f'canonical/M{m}';out.mkdir(parents=True,exist_ok=True)
 d=load(OLD/f'data/M{m}/data.json');source=(ROOT/d['mei']['path']).read_bytes();assert hashlib.sha256(source).hexdigest()==d['mei']['sha256']
 requested=sorted({n for s in d['sections'] for n in s['requested_staves']},key=int)
 options=dict(inputFrom='mei',xmlIdSeed=314159265,breaks='none',condense='none',header='none',footer='none',svgViewBox=True,svgBoundingBoxes=False,pageWidth=18000,pageHeight=60000,adjustPageHeight=True,systemMaxPerPage=1,minLastJustification=0,spacingStaff=10,pageMarginTop=40,pageMarginBottom=40,pageMarginLeft=40,pageMarginRight=40)
 probe=HERE/'canonical-probe'
 if m==3 and (probe/'M3-full-native.svg').exists():
  fixed=(probe/'M3-normalized.mei').read_bytes();svg=(probe/'M3-full-native.svg').read_bytes();selected=load(probe/'manifest.json')['selected_staves']
 else:
  projection=project_stable_staves(source,requested,expected_mei_sha256=d['mei']['sha256']);selected=projection['selected_staff_numbers'];fixed,changes=repair(projection['mei'],m)
  v=verovio.toolkit();assert v.setOptions(options) and v.loadData(fixed.decode());assert v.getPageCount()==1
  svg=repair_svg(v.renderToSVG(1).encode(),m)
 (out/'native.svg').write_bytes(svg);(out/'normalized.mei').write_bytes(fixed)
 root=X.fromstring(svg);mei=X.fromstring(fixed);index=mei_index(fixed);measure_ids={e.get(ID):i+1 for i,e in enumerate(mei.iter(N+'measure'))}
 measures_q={e['raw']:e for e in d['measures']};original_root_id=root.get('id');prefix=f'm{m}-';rootid=prefix+original_root_id
 # Prefix every native id in the frozen scene so two movement scenes can coexist.
 for e in root.iter():
  if e.get('id'):e.set('data-native-id',e.get('id'));e.set('id',prefix+e.get('id'))
  if e.get(XL,'').startswith('#'):e.set(XL,'#'+prefix+e.get(XL)[1:])
  if e.tag==S+'style' and e.text:e.text=e.text.replace('#'+original_root_id,'#'+rootid)
 defs=root.find(S+'defs');style=root.find(S+'style');(out/'defs.svg').write_text(X.tostring(defs,encoding='unicode'));(out/'style.css').write_text(style.text or '')
 system=next(e for e in root.iter(S+'g') if e.get('class')=='system')
 original_ids={e.get('data-native-id') for e in system.iter() if e.get('data-native-id')}
 missing=[n['id'] for n in d['notes'] if n['visible'] and n['engraver_id'] not in original_ids];assert not missing,('missing source note',m,missing[:10])
 controls={};descriptors=[];centers={};unknown=[]
 for measure in [e for e in system if e.get('class')=='measure']:
  key=measure.get('data-native-id');raw=measure_ids[key];staves=[]
  for staff in [e for e in measure if e.get('class')=='staff']:
   native=staff.get('data-native-id');info=index[native];n=info['storage_staff'];paths=[e for e in staff if e.tag==S+'path'];ys=[]
   for path in paths:
    values=re.findall(r'[-+]?(?:\d*\.)?\d+',path.get('d',''))
    if len(values)==4 and abs(float(values[1])-float(values[3]))<1e-6:ys.append(float(values[1]))
   assert ys,('staff lines absent',m,raw,n)
   c=(min(ys)+max(ys))/2
   if n in centers:assert abs(centers[n]-c)<1e-6,('canonical staff drift',m,n)
   centers[n]=c;staves.append(dict(id=native,n=n,center=c,lines=sorted(ys)))
  for e in measure.iter(S+'g'):
   cls=e.get('class','');native=e.get('data-native-id')
   if native in index and cls not in ['staff','note','rest','mRest','layer','accid','dots','artic','stem','clef','keySig','keyAccid','meterSig','tupletNum','tupletBracket']:
    info=index[native]
    if cls in ['beam','chord','tuplet'] or e in list(measure):controls[native]=info
   elif e in list(measure) and cls not in ['staff','barLine','mNum']:
    unknown.append(dict(id=native,cls=cls,raw=raw))
  path=out/f'measures/{raw:04d}.svg';path.parent.mkdir(exist_ok=True);path.write_text(X.tostring(measure,encoding='unicode'))
  descriptors.append(dict(raw=raw,id=key,q=[measures_q[raw]['q'],measures_q[raw]['end']],svg=str(path.relative_to(ROOT)),staves=staves))
 assert not unknown,('Unknown measure objects',m,unknown[:10])
 # Original semantic label groups, not translated labels, define row ownership.
 labels=[]
 for e in mei.iter():
  if e.tag not in [N+'staffDef',N+'staffGrp']:continue
  rows=[e.get('n')] if e.tag==N+'staffDef' else [x.get('n') for x in e.iter(N+'staffDef')]
  rows=[n for n in rows if n in centers]
  label=e.find(N+'label');abbr=e.find(N+'labelAbbr')
  if rows and (label is not None or abbr is not None):labels.append(dict(id=e.get(ID),rows=rows,text=text(label) if label is not None else text(abbr),abbr=text(abbr) if abbr is not None else None))
 # Retain native braces and system start rules as explicit generated templates.
 system_extra=X.Element(S+'g')
 for e in list(system):
  if e.get('class')!='measure':system_extra.append(e)
 (out/'system.svg').write_text(X.tostring(system_extra,encoding='unicode'))
 dump(out/'source.json',dict(movement=m,recipe=1,root_id=rootid,prefix=prefix,native_svg=ref(out/'native.svg'),normalized_mei=ref(out/'normalized.mei'),data=str((OLD/f'data/M{m}/data.json').relative_to(ROOT)),defs=str((out/'defs.svg').relative_to(ROOT)),style=str((out/'style.css').relative_to(ROOT)),system=str((out/'system.svg').relative_to(ROOT)),selected_staves=selected,centers=centers,labels=labels,controls=controls,measures=descriptors,note_coverage=dict(expected_visible=sum(n['visible'] for n in d['notes']),missing=missing),unknown=unknown))
 print('Complete canonical',m,len(descriptors),'measures',len(centers),'rows',len(controls),'controls',flush=True)

if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--movement',type=int);args=a.parse_args()
 for m in ([args.movement] if args.movement else range(1,5)):build(m)
