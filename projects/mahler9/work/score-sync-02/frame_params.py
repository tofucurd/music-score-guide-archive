"""Deterministic source-time commands for native continuous score rendering.
Audio remains the immutable original sample sequence.
"""
from pathlib import Path
import sys,json,math,argparse,hashlib
ROOT=next(p for p in Path(__file__).resolve().parents if (p/'work/score-sync-01/timeline.json').is_file());OLD=ROOT/'work/score-sync-01';NEW=ROOT/'work/score-sync-02'
sys.path.insert(0,str(OLD));from scroll_renderer import clock_curve,LABELS
sys.path.insert(0,str(NEW));from animation import PresenceSchedule,highlight_envelope,PALETTE,ease
from navigation import navigation_states,render_navigation
from dependency_schedule import DependencySchedule
from spacing import SpacingSchedule
from materials import compile_materials
load=lambda p:json.loads(Path(p).read_text())
TRANSLATIONS=load(NEW/'assets/labels.json')
class Frames:
 def __init__(self):
  self.timeline=load(OLD/'timeline.json');self.cache={}
  self.materials=load(NEW/'assets/highlight-strands.json')['display_event_map'];self.colors={};self.ends={};self.domains={}
 def actor(self,m):
  if m not in self.cache:
   data=load(OLD/f'data/M{m}/data.json');geometry=load(NEW/f'canonical/M{m}/geometry-ink-final.json');meta=load(NEW/f'canonical/M{m}/source.json')
   curve,bounds=clock_curve(data['clock'],geometry['axis']);dependency=DependencySchedule(data['sections'],movement=m);sched=SpacingSchedule(dependency.opacity,load(NEW/f'assets/spacing-M{m}.json'),reserve=4,pair_center_floors=[('45','46',2400)] if m==1 else [])
   compiled=compile_materials(m,data['notes'],meta['controls'],self.materials);self.colors[m]={u:r['color'] for u,r in compiled['events'].items()};self.ends[m]=compiled['ends'];self.domains[m]={n['id']:f"{n['range'][0]}:{self.ends[m][n['id']]}:highlight-v1" for n in data['notes']};self.cache[m]=(data,geometry,meta,curve,bounds,sched)
  return self.cache[m]
 def frame(self,frame):
  sample=min(frame*1600,self.timeline['total_samples']-1);mov=next(x for x in self.timeline['movements'] if x['global_range'][0]<=sample<x['global_range'][1]);m=mov['movement'];local=sample-mov['global_range'][0]
  data,g,meta,curve,bounds,sched=self.actor(m);t=local/96000
  # Final source-ink-aware slot reserve and common smooth scale.
  layout=sched.layout(t);cs=min(max(local,bounds[0]),bounds[1]);native_x=float(curve(cs))
  highlights={n['id']:a for n in data['notes'] if (a:=highlight_envelope(t,n['range'][0]/96000,self.ends[m][n['id']]/96000))>0}
  previous_nav=self.actor(m-1)[0]['nav'] if m>1 and local<81600 else None
  nav=render_navigation(navigation_states(data['nav'],local,previous_nav=previous_nav,movement_elapsed_samples=local));section=next(s for s in data['sections'] if s['range'][0]<=local<s['range'][1]);required=set(section['requested_staves']);assert all(layout['weights'][n]==1 for n in required)
  assert math.isfinite(layout['scale']) and layout['scale']>0
  visible=[(int(n),y) for n,y in layout['rows'].items() if layout['weights'][n]>0];assert [n for n,_ in visible]==sorted(n for n,_ in visible)
  scene={'movement':m,'x':native_x,'layout':layout,'offset':0,'opacity':1,'highlights':highlights,'domains':{u:self.domains[m][u] for u in highlights},'colors':{u:self.colors[m][u] for u in highlights if u in self.colors[m]},'translations':TRANSLATIONS}
  scenes=[scene]
  if m>1 and local<81600:
   elapsed=local/96000
   if elapsed<.4:
    oldmov=self.timeline['movements'][m-2];oldframe=(oldmov['global_range'][1]-1)//1600
    oldspec=self.frame(oldframe)['scenes'][-1];u=ease(elapsed/.4);oldspec['opacity']=1-u;oldspec['offset']=-48*u;scenes=[oldspec]
   else:
    u=ease((elapsed-.4)/.45);scene['opacity']=u;scene['offset']=48*(1-u);scenes=[scene]
  return {'frame':frame,'scenes':scenes,'navigation':nav,'cursor':[50,1810],'cursor_opacity':1,'diagnostics':{'global_sample':sample,'movement_local_sample':local,'section':section['id'],'native_curve_bounds':bounds,'required_staffs':sorted(required,key=int),'present_staffs':[n for n,w in layout['weights'].items() if w>0],'fully_visible_staffs':[n for n,w in layout['weights'].items() if w==1],'source_clock':'work/score-sync-01/scroll_renderer.py:clock_curve','color_policy':'72 source-bound strands plus representative cores; explicit ties preserve display identity'}}
 def at(self,m,seconds):
  start=self.timeline['movements'][m-1]['global_range'][0];return self.frame(round((start+round(seconds*96000))/1600))
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--movement',type=int);ap.add_argument('--seconds',type=float);ap.add_argument('--frames',type=int,default=1);ap.add_argument('--output',type=Path);args=ap.parse_args();r=Frames()
 if args.movement:
  first=r.at(args.movement,args.seconds)['frame'];frames=[r.frame(f) for f in range(first,first+args.frames)];out=args.output
 else:
  for name,m,times in [('m1-initial',1,[0,1,3,6,10,15]),('m3-pressure',3,[620.97,621.97,622.47,622.9533333,622.97,622.9866667,623.47,623.97,624.97])]:
   frames=[r.at(m,t) for t in times];out=Path(__file__).with_name(name+'-frames.json');out.write_text(json.dumps({'prototype':'C isolated;603core colors+default;4s lead/trail;shared smooth cap','frames':frames},ensure_ascii=False)+'\n');print(out.relative_to(ROOT),[(x['frame'],x['diagnostics']['section'],len(x['diagnostics']['present_staffs']),round(x['scenes'][0]['layout']['scale'],7)) for x in frames])
  return
 out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps({'frames':frames},ensure_ascii=False)+'\n');print(out)
if __name__=='__main__':main()
