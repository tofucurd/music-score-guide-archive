import math, hashlib, xml.etree.ElementTree as ET

def scale_components(geometry):
    staves=geometry['staves']
    indices={s['id']:i for i,s in enumerate(staves)}
    parents=list(range(len(staves)))
    def find(i):
        while parents[i]!=i:
            parents[i]=parents[parents[i]]
            i=parents[i]
        return i
    def unite(a,b):
        parents[find(b)]=find(a)
    dependencies=geometry.get('staff_dependencies')
    if dependencies is None:
        dependencies=[{'staves':s.get('dependencies') or [s['id']]} for s in staves]
    dependencies=dependencies+[c for c in geometry.get('controls',[]) if len(c['staves'])>1]
    for dep in dependencies:
        ii=[indices[s] for s in dep['staves'] if s in indices]
        if ii:
            for i in range(min(ii),max(ii)):
                unite(i,i+1)
    extents={s['id']:[s['y']-s['height']/2-450,s['y']+s['height']/2+450] for s in staves}
    for note in geometry['notes']:
        y=note.get('y')
        if note['staff'] in extents and isinstance(y,(int,float)) and math.isfinite(y):
            b=extents[note['staff']]
            b[0]=min(b[0],y-750)
            b[1]=max(b[1],y+750)
    components={}
    for i,s in enumerate(staves):
        components.setdefault(find(i),[]).append(s['id'])
    return [{'staves':ids,'top':min(extents[s][0] for s in ids),'bottom':max(extents[s][1] for s in ids)}
            for ids in components.values()]

def window_svg(base,frames):
    comps=scale_components(base['geometry'])
    minimum=min(.22,1640/sum(c['bottom']-c['top']+240 for c in comps))
    left=min(f['x'] for f in frames)-(1344-380)/minimum
    right=max(f['x'] for f in frames)+(3730-1344)/minimum
    measures=base['geometry']['measures']
    retained={m['svg_id'] for m in measures if m['x']+2*m['width']>=left and m['x']-m['width']<=right}
    for f in frames:
        total=sum((c['bottom']-c['top']+240)*math.sqrt(max(f['weights'].get(s,0) for s in c['staves'])) for c in comps)
        scale=min(.22,1640/max(1,total));assert scale>=minimum-1e-12
        a=f['x']-(1344-380)/scale;b=f['x']+(3730-1344)/scale
        assert {m['svg_id'] for m in measures if m['x']+2*m['width']>=a and m['x']-m['width']<=b}<=retained
    ET.register_namespace('','http://www.w3.org/2000/svg');ET.register_namespace('xlink','http://www.w3.org/1999/xlink')
    tree=ET.fromstring(base['svg']);kept={};removed=[]
    for parent in tree.iter():
        for child in list(parent):
            if child.tag.endswith('}g') and 'measure' in child.get('class','').split():
                if child.get('id') not in retained:
                    assert not any(n.tag.endswith('}defs') for n in child.iter())
                    removed.append(child.get('id'));parent.remove(child)
                else:kept[child.get('id')]=hashlib.sha256(ET.tostring(child)).hexdigest()
    svg=ET.tostring(tree,encoding='unicode')
    for n in ET.fromstring(svg).iter():
        if n.get('id') in kept:assert hashlib.sha256(ET.tostring(n)).hexdigest()==kept[n.get('id')]
    return svg,{'native_viewport':[380,3730],'fixed_cursor':1344,'minimum_scale':minimum,
                'all_frame_visible_measures_retained':True,'retained_measure_subtrees_unchanged':True,
                'retained':len(retained),'removed':len(removed),'source_svg_bytes':len(base['svg'].encode()),'windowed_svg_bytes':len(svg.encode())}
