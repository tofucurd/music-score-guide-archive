"""Bound attention before routing; ramps occupy capacity as well as held lines."""
import copy
import itertools
import json
import math
import re

POLICY = {'maximum_points': 2, 'maximum_branches': 3,
          'minimum_settled_seconds': 2., 'minimum_onset_lead_seconds': .15,
          'minimum_extend_seconds': .35, 'default_extend_seconds': .65,
          'retract_seconds': .35}


def bound_connections(windows, routing_conflicts=()):
    grouped, omitted = {}, []
    for original in windows:
        # Reopening an already explained sustained line after a page change
        # spends attention without identifying a new musical entrance.
        if original['continuation']:
            omitted.append({'index': original['index'], 'reason': 'already introduced before page transition'})
            continue
        w = copy.deepcopy(original)
        key = json.dumps([w['page_id'],w['block'],w['keyword'],
                          w.get('keyword_occurrence',0),w.get('semantic_event')],ensure_ascii=False)
        w['semantic_group'] = key
        grouped.setdefault(key,[]).append(w)
    groups = []
    for key, branch in grouped.items():
        for attr in ['from','full_at','hold_until','to','source_start','source_end']:
            assert len({w[attr] for w in branch}) == 1, (key,attr)
        groups.append({'key':key,'branches':branch,**{k:branch[0][k] for k in
                       ['from','full_at','hold_until','to','source_start','source_end','theme']}})
    groups.sort(key=lambda g:(g['from'],g['key']))
    accepted, adjustments = [], []
    def fits(gs):
        return len(gs)<=POLICY['maximum_points'] and sum(len(g['branches']) for g in gs)<=POLICY['maximum_branches']
    for _, iterator in itertools.groupby(groups,key=lambda g:g['from']):
        batch=list(iterator);requested=batch[0]['from']
        assert fits(batch), ('simultaneous entrances exceed capacity',batch)
        active=[g for g in accepted if g['to']>requested+1e-6]
        if not fits(active+batch):
            candidates=[]
            for count in range(1,len(active)+1):
                for victims in itertools.combinations(active,count):
                    remaining=[g for g in active if g not in victims]
                    if not fits(remaining+batch):continue
                    start=max(requested,*(max(g['full_at']+POLICY['minimum_settled_seconds'],
                                              g['source_start']+.2)+POLICY['retract_seconds'] for g in victims))
                    duration=min(POLICY['default_extend_seconds'],
                                 min(g['source_start'] for g in batch)-POLICY['minimum_onset_lead_seconds']-start)
                    if duration<POLICY['minimum_extend_seconds']-1e-6:continue
                    # Prefer retiring a broad theme already introduced over
                    # a new short motif; otherwise retire the shorter source.
                    priorities=sum(not bool(re.fullmatch(r'theme\d+',g['theme'])) for g in victims)
                    cost=(start-requested,count,priorities,sum(g['full_at'] for g in victims),
                          sum(g['source_end'] for g in victims),tuple(g['key'] for g in victims))
                    candidates.append((cost,victims,start,duration))
            if not candidates:raise ValueError(('No anticipatory bounded schedule',requested,batch,active))
            _,victims,start,duration=min(candidates,key=lambda c:c[0])
            for g in victims:
                old_to=g['to'];g['to']=min(g['to'],start);g['hold_until']=g['to']-POLICY['retract_seconds']
                adjustments.append({'semantic_group':g['key'],'action':'retire for new entrance',
                                    'old_to':old_to,'hold_until':g['hold_until'],'to':g['to']})
            for g in batch:
                if start!=requested:
                    adjustments.append({'semantic_group':g['key'],'action':'shorter entrance animation',
                                        'old_from':requested,'from':start,'extend_seconds':duration})
                g['from']=start;g['full_at']=start+duration
        accepted+=batch
    # Geometric planning can report incompatible endpoint orders. Preserve
    # the newer onset and retire the already introduced semantic group whole.
    # This is an explicit temporal constraint, never a hidden renderer drop.
    for conflict in routing_conflicts:
        pair=[next(g for g in accepted if any(w['target_id']==target for w in g['branches']))
              for target in conflict['targets']]
        older,newer=sorted(pair,key=lambda g:g['from'])
        if older['to']<=newer['from']:continue
        hold=newer['from']-POLICY['retract_seconds']
        assert hold>=max(older['full_at']+POLICY['minimum_settled_seconds'],
                         older['source_start']+.2)-1e-6, conflict
        adjustments.append({'semantic_group':older['key'],'action':'retire for routing conflict',
                            'old_to':older['to'],'hold_until':hold,'to':newer['from'],
                            'conflict':conflict})
        older['hold_until']=hold;older['to']=newer['from']
    bounded=[]
    for g in accepted:
        for w in g['branches']:
            for attr in ['from','full_at','hold_until','to']:w[attr]=round(g[attr],6)
            w['lead_seconds']=round(w['source_start']-w['full_at'],6)
            w['settled_seconds']=round(w['hold_until']-w['full_at'],6)
            assert w['settled_seconds']>=POLICY['minimum_settled_seconds']-1e-5,w
            assert w['lead_seconds']>=POLICY['minimum_onset_lead_seconds']-1e-5,w
            assert w['full_at']<=w['source_start']<=w['hold_until'],w
            bounded.append(w)
    boundaries=sorted({v for w in bounded for v in [w['from'],w['to']]})
    occupancy=[]
    for a,b in zip(boundaries,boundaries[1:]):
        active=[w for w in bounded if w['from']<=(a+b)/2<w['to']]
        points=len({w['semantic_group'] for w in active})
        assert points<=2 and len(active)<=3,(a,b,active)
        occupancy.append({'from':a,'to':b,'points':points,'branches':len(active),
                          'windows':[w['index'] for w in active]})
    return bounded,{'policy':dict(POLICY),'adjustments':adjustments,'omitted':omitted,
                    'maximum_points':max(x['points'] for x in occupancy),
                    'maximum_branches':max(x['branches'] for x in occupancy),
                    'occupancy':occupancy}


def add_routing_references(specs, frame_at, fps=30):
    """Stable absolute-time geometry for jointly planning every overlap set."""
    cached={}
    for name,spec in specs.items():
        p=spec['guide_payload'];key=p.get('reading_track_id',name)
        if key in cached:
            p['routing_reference_frames']=copy.deepcopy(cached[key]);continue
        windows=p['connection_windows'];edges=sorted({v for w in windows for v in [w['from'],w['to']]})
        samples=[];seen=set()
        for a,b in zip(edges,edges[1:]):
            active=[w for w in windows if w['from']<=(a+b)/2<w['to']]
            if not active:continue
            identity=tuple(sorted(w['index'] for w in active))
            if identity in seen:continue
            seen.add(identity)
            ready=max(a,max(w['full_at'] for w in active))
            # Include both ends of a shared interval so a route is not chosen
            # from only one fortunate placement in the moving score.
            times=[min(b-.001,max(a+.001,ready)), b-.001]
            if len(active)==1:
                # A solitary line still encounters moving staff geometry.
                # A midpoint-only choice can lose its lane near the end.
                times += [(a+b)/2]
                times += [w['hold_until'] for w in active if a<w['hold_until']<b]
            for t in sorted(set(round(v,6) for v in times)):
                samples.append({'seconds':t,'window_indices':list(identity),'frame':frame_at(t)})
        # Concurrency starts during the extension ramp, before full_at.
        # Retain the old settled samples, but also check both actual video
        # frames adjoining every transition into/out of a concurrent set.
        # A short overlap can otherwise collapse to one lucky end sample.
        recorded={r['seconds'] for r in samples}
        for edge in edges:
            before=[w for w in windows if w['from']<edge<=w['to']]
            after=[w for w in windows if w['from']<=edge<w['to']]
            if max(len(before),len(after))<2:continue
            first=math.ceil(edge*fps-1e-9)
            for ordinal in [first-1,first]:
                t=ordinal/fps
                active=sorted(w['index'] for w in windows if w['from']<=t<w['to'])
                if active and t not in recorded:
                    samples.append({'seconds':t,'window_indices':active,'frame':frame_at(t)})
                    recorded.add(t)
        samples.sort(key=lambda r:r['seconds'])
        p['routing_reference_frames']=samples;cached[key]=samples


def overlapping_window_components(windows):
    """Entire temporal coupling components, independent of output chunks."""
    result=[];end=-float('inf')
    for w in sorted(windows,key=lambda w:(w['from'],w['index'])):
        if not result or w['from']>=end-1e-9:
            result.append([]);end=w['to']
        result[-1].append(w);end=max(end,w['to'])
    return result


def retain_routing_components(payload,start,end):
    """Retain all partners and original reference samples of visible windows."""
    components=overlapping_window_components(payload['connection_windows'])
    selected=[c for c in components if any(w['from']<=end and w['to']>=start for w in c)]
    ids={w['index'] for c in selected for w in c}
    payload['connection_windows']=[w for w in payload['connection_windows'] if w['index'] in ids]
    refs=[]
    for ref in payload['routing_reference_frames']:
        if ids.intersection(ref['window_indices']):
            assert set(ref['window_indices'])<=ids,'partial routing component'
            refs.append(ref)
    payload['routing_reference_frames']=refs
    payload['routing_scope']={'start':start,'end':end,'policy':'Complete overlap components and their unchanged global reference samples; independent component route solving','components':[[w['index'] for w in c] for c in selected]}
    return payload
