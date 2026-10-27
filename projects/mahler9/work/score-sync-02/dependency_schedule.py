"""Mergeable source-time context scheduling; alpha and allocation are independent.
The default M1 requirements conservatively cover ALL viewports at scale>=.01.
The previous exact2400/1780 fixed-point result is retained separately, not reused
for arbitrary dynamic envelope metrics or reduced height.
No rendering or audio modification. Use pair metrics>=2400 native for M1 45/46.
"""
from pathlib import Path
import importlib.util,json
ROOT=next(p for p in Path(__file__).resolve().parents if (p/'work/score-sync-02/animation.py').is_file())
_spec=importlib.util.spec_from_file_location('dependency_animation',ROOT/'work/score-sync-02/animation.py');_a=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(_a)
PresenceSchedule=_a.PresenceSchedule
# Exact source-sample intervals, not rounded seconds. Context has the same 96k clock.
LEGACY_2400_1780_FIXED_POINT_RANGES=((17803200,27283200),(32883200,39236800),(60086400,75081600),(122724800,134027200),(143497600,155212800))
# Broader default supports final height1680 and dynamic envelopes, provided scale>=.01.
M1_CONTEXT_RANGES=((385600,78057600),(112092800,163288000))
MINIMUM_CENTER_GAPS={("45","46"):2400.}
def dependency_requirements(movement):
 return [dict(id=f'M1-beam45-46-context-{i}',range=[a,b],requested_staves=['45','46'],reason='fixed_point_actual_visible_beamSpan_member_closure') for i,(a,b) in enumerate(M1_CONTEXT_RANGES)] if movement==1 else []

class DependencySchedule:
 def __init__(self,sections,*,movement,lead=4.,trail=4.,allocation_lead=8.,allocation_trail=8.,rate=96000,extra_requirements=None):
  if allocation_lead<lead or allocation_trail<trail:raise ValueError('Allocation may not enter later or leave earlier than opacity')
  if rate!=96000 and movement==1 and extra_requirements is None:raise ValueError('Frozen M1 dependency ranges are96k source samples')
  self.lead=lead;self.trail=trail;self.minimum_scale=.01
  self.movement=movement;self.context=dependency_requirements(movement) if extra_requirements is None else extra_requirements
  self.sections=list(sections);all_sections=self.sections+self.context
  self.opacity=PresenceSchedule(all_sections,lead=lead,trail=trail,rate=rate)
  self.allocation=PresenceSchedule(all_sections,lead=allocation_lead,trail=allocation_trail,rate=rate)
  self.order=self.allocation.order;self.intervals=self.opacity.intervals
 def weights(self,t):return self.opacity.weights(t)
 def allocation_weights(self,t):return self.allocation.weights(t)
 def layout(self,t,top=140,height=1680,metrics=None,max_scale=.11):
  metrics=dict(metrics or {})
  if self.movement==1:
   for n in ['45','46']:metrics[n]=max(2400.,float(metrics.get(n,2400.)))
  L=self.allocation.layout(t,top=top,height=height,metrics=metrics,max_scale=max_scale)
  if L['scale']+1e-12<self.minimum_scale:raise ValueError('Scale below dependency viewport floor; recompile wider intervals')
  L['allocation_weights']=dict(L['weights']);L['weights']=self.opacity.weights(t)
  L['dependency_context_ids']=[s['id'] for s in self.context if s['range'][0]/96000<=t<=s['range'][1]/96000]
  return L
