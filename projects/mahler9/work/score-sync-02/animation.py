"""Continuous, source-time-only layout and color primitives."""
import math

BLUE='#287D9F'
PALETTE={'main':'#C94732','purple':'#8650B6','green':'#27835D','ochre':'#AA7200'}

def ease(u):
 u=min(1.0,max(0.0,float(u)))
 return u*u*u*(10+u*(-15+6*u))

class PresenceSchedule:
 def __init__(self,sections,lead=1.2,trail=1.2,rate=96000):
  self.lead=float(lead);self.trail=float(trail);self.intervals={}
  for section in sections:
   a,b=(x/rate for x in section['range'])
   for n in set(section['requested_staves']):self.intervals.setdefault(str(n),[]).append((a,b))
  for n,rows in self.intervals.items():
   merged=[]
   for a,b in sorted(rows):
    if merged and a-merged[-1][1]<=self.lead+self.trail:merged[-1]=(merged[-1][0],max(b,merged[-1][1]))
    else:merged.append((a,b))
   self.intervals[n]=merged
  self.order=sorted(self.intervals,key=int)
 def weights(self,t):
  result={}
  for n in self.order:
   alpha=0.0
   for a,b in self.intervals[n]:
    if a<=t<=b:alpha=1.0;break
    if a-self.lead<t<a:alpha=max(alpha,ease((t-a+self.lead)/self.lead))
    elif b<t<b+self.trail:alpha=max(alpha,1-ease((t-b)/self.trail))
   result[n]=alpha
  return result
 def layout(self,t,top=50,height=1780,metrics=None,max_scale=.11):
  weights=self.weights(t);metrics=metrics or {};heights={n:float(metrics.get(n,2400)) for n in self.order}
  total=sum(weights[n]*heights[n] for n in self.order)
  # A deterministic finite layout remains when all notation has left the scene.
  scale=max_scale/(1+(max_scale*total/height)**12)**(1/12)
  used=total*scale;offset=top+(height-used)/2;rows={}
  for n in self.order:
   h=weights[n]*heights[n]*scale;rows[n]=offset+h/2;offset+=h
  return dict(rows=rows,weights=weights,scale=scale,content_top=top+(height-used)/2,content_bottom=top+(height+used)/2)

class MaterialColors:
 def __init__(self,event_materials,family_slots):
  self.event_materials=dict(event_materials);self.family_slots=dict(family_slots)
  unknown=set(self.family_slots.values())-set(PALETTE)
  if unknown:raise ValueError('Unknown palette slots: '+str(unknown))
 def color(self,event_id):
  family=self.event_materials.get(event_id)
  return PALETTE[self.family_slots.get(family,'main')]

def highlight_envelope(t,onset,end,attack=.06,release=.1):
 if not onset<=t<end or end<=onset:return 0.0
 a=min(attack,(end-onset)*.3);r=min(release,(end-onset)*.3)
 return min(ease((t-onset)/a),ease((end-t)/r))
