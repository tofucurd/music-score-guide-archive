#!/usr/bin/env python3
"""Materialize and use the archived final snapshots; never realign them."""
from pathlib import Path
import argparse,gzip,hashlib,json,os,shutil,subprocess,sys,wave

ROOT=Path(__file__).resolve().parent
VENDOR=ROOT/'vendor/score-sync-video'
os.environ['SCORE_SYNC_ENGINE']=str(VENDOR)
os.environ['SCORE_SYNC_VENDOR']=str(VENDOR)
sys.path.insert(0,str(VENDOR/'scripts'))

def read(p):return json.loads(Path(p).read_text())
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
 return h.hexdigest()
def write(p,v):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
def safe(root,rel):
 p=(root/rel).resolve();p.relative_to(root.resolve());return p
def restore(name):
 source=ROOT/'projects'/name;dest=ROOT/'workspaces'/name
 if name=='mahler9':
  raise SystemExit('Mahler IX has an explicitly documented missing final color map. See projects/mahler9/README.md; its source-only restore entry remains inside that directory.')
 manifest=read(source/'inventory.json')
 for row in manifest['files']:
  target=safe(dest,row['path']);target.parent.mkdir(parents=True,exist_ok=True)
  payload=safe(source,row['archive_path'])
  if row['compressed']:
   with gzip.open(payload,'rb') as inp,target.open('wb') as out:shutil.copyfileobj(inp,out)
  else:shutil.copy2(payload,target)
  if sha(target)!=row['sha256']:raise ValueError('Archived snapshot checksum mismatch: '+row['path'])
 shutil.copy2(source/'project.json',dest/'project.json')
 if (source/'code').exists():shutil.copytree(source/'code',dest/'code',dirs_exist_ok=True)
 return dest

def load_cfg(name):
 from score_sync import workflow
 root=ROOT/'workspaces'/name
 if not (root/'project.json').exists():raise SystemExit('First run: python archive.py restore '+name)
 return root,workflow.load_project(root/'project.json')

def prepare_audio(name,external):
 from score_sync.audio import prepare_audio as decode
 root,cfg=load_cfg(name);sources=read(ROOT/'projects'/name/'sources.json')['external_files']
 for m in cfg['movements']:
  expected=read(root/f'.score-sync/{m["id"]}/audio.json')
  rel=next(x for x in sources if x['kind']=='audio' and (x.get('movement')==m['id'] or (root/x['path']).resolve()==Path(m['audio'])))
  source=safe(Path(external),rel['path'])
  if not source.is_file():raise FileNotFoundError(source)
  if sha(source)!=rel['sha256']:raise ValueError('Recording differs from the archived performance: '+m['id'])
  item={**m,'audio':str(source)};actual=decode(item,root/f'.score-sync/{m["id"]}')
  for key in ['sample_rate','channels','bits','samples']:
   if actual[key]!=expected[key]:raise ValueError('Prepared audio '+key+' differs: '+m['id'])
 print('Prepared original PCM; frozen score and alignment retained.')

def import_file(name,path):
 import importlib.util
 spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec)
 sys.modules[name]=module;spec.loader.exec_module(module);return module

def render(name):
 from score_sync import visual,workflow
 root,cfg=load_cfg(name);total,timeline=workflow.build_timeline(cfg)
 for m in cfg['movements']:
  if not (root/f'.score-sync/{m["id"]}/audio.wav').is_file():raise SystemExit('Run prepare-audio with the external recordings first.')
 original=visual.run_browser
 if name=='beethoven9':
  vocal=import_file('vocal_programme',root/'research/intake/vocal_programme.py')
  material=import_file('archive_material',root/'research/material-regions-full/material_programme.py')
  pruning=import_file('archive_pruning',root/'research/archived_pruning.py')
  renderer=root/'research/material-regions-full/browser_preview.mjs'
  def browser(spec,output,mode='video'):
   for i,scene in enumerate(spec['scenes']):
    states=[a['state'] for f in spec['frames'] for a in f['actors'] if a['scene']==i]
    scene['svg'],_=pruning.window_svg(scene,states)
   vocal.prepare_spec(spec);material.prepare_spec(spec,registry_path=root/'content/material-regions/index.json')
   path=output.with_suffix('.scene.json');write(path,spec)
   try:subprocess.run(['node',str(renderer),'--spec',str(path),'--output',str(output),'--mode',mode],check=True)
   finally:path.unlink(missing_ok=True)
   return output
  visual.run_browser=browser
 out=root/'output';chunks=out/'chunks';chunks.mkdir(parents=True,exist_ok=True);entries=[]
 for start in range(0,total,1800):
  count=min(1800,total-start);target=chunks/f'{start:09d}.mov'
  if not target.exists():
   partial=target.with_suffix('.partial.mov')
   visual.render_program(cfg,[Path(t['dir']) for t in timeline],partial,start,count,2160,True)
   partial.replace(target)
  entries.append(target)
 visual.run_browser=original
 listing=out/'concat.ffconcat';listing.write_text(''.join("file '"+str(p.resolve())+"'\n" for p in entries))
 if name=='beethoven9':
  audio=out/'original-pcm.wav';position=0;chapters=[]
  with wave.open(str(audio),'wb') as dst:
   dst.setparams((2,2,44100,0,'NONE','not compressed'))
   for m in cfg['movements']:
    with wave.open(str(root/f'.score-sync/{m["id"]}/audio.wav'),'rb') as src:
     if (src.getnchannels(),src.getsampwidth(),src.getframerate())!=(2,2,44100):raise ValueError('Unexpected PCM format')
     n=src.getnframes();chapters.append({'id':m['id'],'title':m['title'],'start_sample':position,'end_sample':position+n});position+=n
     for block in iter(lambda:src.readframes(262144),b''):dst.writeframesraw(block)
  manifest={'sample_rate':44100,'bits':16,'channels':2,'samples':position,'chapters':chapters}
 else:
  audio=workflow.master_audio(cfg,out);manifest=read(out/'audio-manifest.json')
 metadata=workflow.write_chapters(manifest,out);target=out/'score-sync-2160p60.mov'
 cmd=workflow.final_mux_command(listing,audio,metadata,target,manifest)
 cmd[cmd.index('-safe')+1]='0';cmd[-1:-1]=['-movie_timescale','90000']
 subprocess.run(cmd,check=True);print(target)

def covers(name):
 from score_sync import visual,workflow
 from score_sync.covers import build_cover_specs
 root,cfg=load_cfg(name)
 if name=='beethoven7':
  out=root/'output/covers';out.mkdir(parents=True,exist_ok=True)
  # The original final cover recipe keeps its proven absolute text positions.
  source=(root/'code/build_reference_cover.py').read_text()
  source=source.replace("ROOT/f'output/visual-revision-04/covers/", "ROOT/f'output/covers/")
  # This is the archived project recipe, invoked only at the operator's request.
  exec(compile(source,str(root/'code/build_reference_cover.py'),'exec'),{'__file__':str(root/'code/build_reference_cover.py'),'__name__':'__main__'})
 else:
  out=root/'output/covers';out.mkdir(parents=True,exist_ok=True)
  m=next(m for m in cfg['movements'] if m['id']==cfg['cover']['movement'])
  b=visual.bundle(cfg,root/f'.score-sync/{m["id"]}')
  for aspect,spec in build_cover_specs(cfg,b).items():visual.run_browser(spec,out/f'封面-{aspect}.svg','cover')

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['restore','prepare-audio','render','covers','show-inputs']);p.add_argument('project',choices=['beethoven7','beethoven9','mahler9']);p.add_argument('--sources',type=Path)
 a=p.parse_args()
 if a.action=='show-inputs':
  path=ROOT/'projects'/a.project/('external-inputs.json' if a.project=='mahler9' else 'sources.json');print(path.read_text());return
 if a.action=='restore':print(restore(a.project));return
 if a.project=='mahler9':raise SystemExit('See projects/mahler9/README.md for the missing-data boundary and original final recipes.')
 if a.action=='prepare-audio':
  if not a.sources:p.error('prepare-audio requires --sources')
  prepare_audio(a.project,a.sources)
 elif a.action=='render':render(a.project)
 elif a.action=='covers':covers(a.project)
if __name__=='__main__':main()
