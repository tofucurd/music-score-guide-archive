"""Source-envelope spacing candidate. Native glyphs remain rigid.

Geometry contract: staff_boxes are canonical-world per measure. A storage staff
bbox containing cross-staff notes is not a valid rigid-row envelope. Supply
owned_staff_boxes for those rows, or strict compilation fails. control_boxes
must include complete single-staff controls; multi-staff connectors retain their
separate endpoint/beam constraint solver. No unknown box is silently ignored.
"""
from bisect import bisect_left,bisect_right
import math

def ease(u):
    u=max(0.,min(1.,u));return u*u*u*(10+u*(-15+6*u))

def _bracket(values,x,upper=False):
    i=(bisect_left(values,x) if upper else bisect_right(values,x)-1)
    return max(0,min(len(values)-1,i))

def _sample_q(clock,sample):
    times=[p[0] for p in clock];i=_bracket(times,sample)
    if i==len(clock)-1:return float(clock[i][1])
    a,q=clock[i];b,r=clock[i+1]
    return float(q+(r-q)*max(0.,min(1.,(sample-a)/(b-a))))

def compile_profiles(data,geometry,meta,*,control_boxes=None,controls_complete=False,
                     strict=True,allow_conservative_cross=False,padding=90.,baseline_above=480.,baseline_below=480.,
                     context_min_scale=.01,lead=4.,trail=4.,reserve=1.,rate=96000):
    """Per-section stable asymmetric envelopes over safe visible-score context.

    control_boxes = [{id, raw?, rows:[n], global:bool, x,y,width,height}].
    Bounds must include native stroke/filter extent; getBBox alone excludes
    stroke, so padding covers ordinary strokes but not arbitrary SVG filters.
    Geometry note_boxes are used by DISPLAY staff; cross-staff parent bbox is
    rejected unless owned_staff_boxes supplies a decontaminated row bbox.
    context_min_scale is an asserted lower bound on actual rendering scale.
    Runtime layout fails below it rather than showing unmeasured future notes.
    """
    if context_min_scale<=0:raise ValueError('Positive context_min_scale required')
    if baseline_above<=0 or baseline_below<=0 or padding<0:raise ValueError('Positive baselines and nonnegative padding required')
    centers={str(k):float(v) for k,v in meta['centers'].items()}
    issues=[];warnings=[]
    if control_boxes is None:control_boxes=geometry.get('control_boxes')
    if control_boxes is None or not controls_complete:
        issues.append('single-staff control bbox completeness not certified')
    control_boxes=control_boxes or []
    notes={n['engraver_id']:n for n in data.get('notes',[])}
    contaminated={(int(n['measure']),str(n['storage_staff'])) for n in notes.values() if n['staff']!=n['storage_staff']}
    owned={(int(b['raw']),str(b['n'])):b for b in geometry.get('owned_staff_boxes',[])}
    boxes=[]
    for b in geometry.get('staff_boxes',[]):
        key=(int(b['raw']),str(b['n']))
        if key in contaminated:
            if key not in owned and not allow_conservative_cross:
                issues.append(f'cross-staff contaminated storage bbox raw={key[0]} row={key[1]} requires owned_staff_boxes')
                continue
            if key in owned:b=owned[key]
            else:warnings.append(f'conservative cross-staff parent envelope raw={key[0]} row={key[1]}; display-note bboxes separately assigned')
        boxes.append(dict(b,rows=[str(b['n'])],owner_kind='rigid_staff'))
    if not geometry.get('staff_boxes'):issues.append('staff_boxes missing')
    for key,b in geometry.get('note_boxes',{}).items():
        n=notes.get(key)
        if n is None:issues.append('note bbox missing source binding '+key);continue
        boxes.append(dict(b,raw=n['measure'],rows=[str(n['staff'])],owner_kind='display_note'))
    for b in control_boxes:
        if b.get('global'):continue
        rows=list(dict.fromkeys(str(n) for n in b.get('rows',[])))
        if len(rows)==1:boxes.append(dict(b,rows=rows,owner_kind='single_staff_control'))
        elif not rows:issues.append('control lacks explicit row '+str(b.get('id')))
        # Multi-row bbox cannot become one row's rigid envelope. Separate solver.
    if strict and issues:raise ValueError('; '.join(issues[:12]))
    axis=geometry['axis'];qs=[p[0] for p in axis];profiles=[]
    context_seconds=max(lead,trail)+reserve
    for section in data['sections']:
        a,b=section['range'];qa=_sample_q(data['clock'],max(0,a-context_seconds*rate));qb=_sample_q(data['clock'],b+context_seconds*rate)
        # Outward knot bracketing conservatively contains monotone PCHIP scroll.
        xa=axis[_bracket(qs,qa)][1];xb=axis[_bracket(qs,qb,True)][1]
        xlo=xa-(1344-380)/context_min_scale;xhi=xb+(3730-1344)/context_min_scale
        env={n:{'above':float(baseline_above),'below':float(baseline_below)} for n in centers}
        counts={n:0 for n in centers}
        for box in boxes:
            if box['x']+box['width']<xlo or box['x']>xhi:continue
            n=box['rows'][0]
            if n not in centers:issues.append('bbox unknown display row '+n);continue
            y=box['y'];bottom=y+box['height'];center=centers[n]
            env[n]['above']=max(env[n]['above'],center-y+padding)
            env[n]['below']=max(env[n]['below'],bottom-center+padding)
            counts[n]+=1
        profiles.append({'id':section['id'],'range_seconds':[a/rate,b/rate],
                         'envelopes':env,'context_x':[xlo,xhi],
                         'bbox_counts':counts,'context_min_scale':context_min_scale})
    if strict and issues:raise ValueError('; '.join(issues[:12]))
    return {'profiles':profiles,'issues':sorted(set(issues)),'warnings':sorted(set(warnings)),
            'controls_complete':bool(controls_complete),'strict_certified':strict and not issues,
            'certification_scope':'conservative supplied rigid-row bbox containment only; not painted-ink tightness, transformed multirow connector clearance, or visual readability approval',
            'baseline_above':baseline_above,'baseline_below':baseline_below,
            'context_min_scale':context_min_scale,'rate':rate}

class SpacingSchedule:
    """C2 upper-envelope and pre-reserved native slots, independent from opacity.

    profiles plateau while section notation can be visible, not just sounding.
    Positive-baseline Lp upper envelope >= each fully active section need.
    It avoids max/min derivative corners and additive whole-envelope doubling.
    reserve slots reach full extent BEFORE alpha begins, and shrink only AFTER
    alpha becomes zero. This protects active rows from silent incoming glyphs.
    """
    def __init__(self,presence,compiled,*,reserve=1.,power=8,baseline_above=None,baseline_below=None,pair_center_floors=()):
        if power<3 or reserve<=0:raise ValueError('power>=3 and positive reserve required')
        self.presence=presence;self.compiled=compiled;self.profiles=compiled['profiles']
        self.base_a=baseline_above or compiled.get('baseline_above',480.)
        self.base_b=baseline_below or compiled.get('baseline_below',480.)
        self.power=power;self.reserve=reserve
        self.order=presence.order;self.slot_intervals={};self.pair_center_floors=tuple(pair_center_floors)
        for n,intervals in presence.intervals.items():
            expanded=[(a-presence.lead,b+presence.trail) for a,b in intervals]
            merged=[]
            for a,b in expanded:
                if merged and a-merged[-1][1]<=2*reserve:merged[-1]=(merged[-1][0],max(b,merged[-1][1]))
                else:merged.append((a,b))
            self.slot_intervals[n]=merged
    @staticmethod
    def _plateau(t,a,b,lead,trail):
        if t<a:return ease((t-a+lead)/lead) if lead>0 else 0.
        if t<=b:return 1.
        return 1-ease((t-b)/trail) if trail>0 else 0.
    def envelopes(self,t):
        p=self.power;acc={n:[self.base_a**p,self.base_b**p] for n in self.order}
        for profile in self.profiles:
            a,b=profile['range_seconds']
            # Full target envelope through alpha lead/trail; C2 ramp outside it.
            w=self._plateau(t,a-self.presence.lead,b+self.presence.trail,self.reserve,self.reserve)
            if not w:continue
            for n in self.order:
                need=profile['envelopes'][n]
                acc[n][0]+=max(0.,need['above']**p-self.base_a**p)*w
                acc[n][1]+=max(0.,need['below']**p-self.base_b**p)*w
        result={n:{'above':a**(1/p),'below':b**(1/p)} for n,(a,b) in acc.items()}
        for upper,lower,floor in self.pair_center_floors:
            upper,lower=str(upper),str(lower)
            if upper not in result or lower not in result:raise ValueError('Pair row absent')
            d=result[upper]['below']+result[lower]['above']
            # Smooth upper maximum: no hard clamp derivative corner. Full slots
            # then have center gap >= floor (intervening slots only add space).
            target=(d**12+float(floor)**12)**(1/12);extra=(target-d)/2
            result[upper]['below']+=extra;result[lower]['above']+=extra
        return result
    def space_weights(self,t):
        return {n:max((self._plateau(t,a,b,self.reserve,self.reserve) for a,b in rows),default=0.) for n,rows in self.slot_intervals.items()}
    def layout(self,t,top=140.,height=1680.,max_scale=.11,min_staff_space_px=None):
        alpha=self.presence.weights(t);spaces=self.space_weights(t);env=self.envelopes(t)
        total=sum(spaces[n]*(env[n]['above']+env[n]['below']) for n in self.order)
        # Smooth upper bound, <= both max_scale and height/total, including zero.
        scale=max_scale/(1+(max_scale*total/height)**12)**(1/12)
        if scale+1e-12<self.compiled.get('context_min_scale',0.):
            raise ValueError('Scale below measured context floor; recompile wider bbox context')
        if min_staff_space_px is not None and 180*scale<min_staff_space_px:
            raise ValueError('Required native staff space unreadable; no active row may be omitted')
        used=total*scale;offset=top+(height-used)/2;rows={}
        for n in self.order:
            if alpha[n]>1e-12 and spaces[n]<1-1e-9:raise AssertionError('Visible glyph before full slot reservation '+n)
            rows[n]=offset+spaces[n]*env[n]['above']*scale
            offset+=spaces[n]*(env[n]['above']+env[n]['below'])*scale
        return dict(rows=rows,weights=alpha,space_weights=spaces,scale=scale,envelopes=env,
                    content_top=top+(height-used)/2,content_bottom=top+(height+used)/2,
                    diagnostics={'native_staff_space_px':180*scale,'bbox_profile_certified':self.compiled.get('strict_certified',False)})
