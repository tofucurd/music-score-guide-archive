"""One display identity per physical tied sustain. No pitch/instrument guessing."""
def compile_materials(movement,notes,controls,display_map):
 by_native={n['engraver_id']:n for n in notes};parent={n['id']:n['id'] for n in notes}
 def find(k):
  if parent[k]!=k:parent[k]=find(parent[k])
  return parent[k]
 for key,c in controls.items():
  if c['tag']!='tie':continue
  if c['start'] not in by_native or c['end'] not in by_native:raise ValueError('Unresolved source tie '+key)
  a,b=(by_native[c[k]]['id'] for k in ['start','end']);parent[find(b)]=find(a)
 groups={}
 for n in notes:groups.setdefault(find(n['id']),[]).append(n)
 events={};ends={};decisions=[]
 for group in groups.values():
  group.sort(key=lambda n:(n['range'][0],n['id']));end=max(n['range'][1] for n in group)
  chosen=[(n['id'],display_map[f"M{movement}/{n['id']}"]) for n in group if f"M{movement}/{n['id']}" in display_map]
  if chosen:
   identity=dict(chosen[0][1])
   if len({x['identity_id'] for _,x in chosen})>1:decisions.append(dict(chain=[n['id'] for n in group],rule='earliest explicit source-bound identity persists through tie',chosen=identity,alternatives=chosen))
   for n in group:events[n['id']]=identity
  for n in group:ends[n['id']]=end
 return dict(events=events,ends=ends,decisions=decisions,tied_chains=sum(len(g)>1 for g in groups.values()))
