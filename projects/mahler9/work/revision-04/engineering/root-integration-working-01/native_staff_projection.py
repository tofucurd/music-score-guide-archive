"""Display-only native re-layout input with whole-phrase stable staff identity.

The complete corrected source remains authoritative. This projection never
chooses a pedagogical bundle, edits note contents, or assigns acoustic times.
"""
import hashlib
import xml.etree.ElementTree as E
from control_ownership import Ownership
from _finite_projection import NS, ID, require, canonical, _contexts
from mei_serialization import serialize_mei

GLOBAL_CONTROLS={NS+'tempo',NS+'reh'}


def project_stable_staves(mei, staff_numbers, *, expected_mei_sha256):
    require(hashlib.sha256(mei).hexdigest()==expected_mei_sha256,'source MEI hash changed')
    requested=list(staff_numbers)
    require(requested and len(set(requested))==len(requested),'empty or duplicate requested rows')
    require(all(isinstance(n,str) and n.isdigit() and int(n)>0 for n in requested),'invalid staff number')
    root=E.fromstring(mei);graph=Ownership(root)
    first_definition=next(root.iter(NS+'scoreDef'),None)
    require(first_definition is not None,'score definition missing')
    ordered=[s.get('n') for s in first_definition.iter(NS+'staffDef')]
    require(len(ordered)==len(set(ordered)),'ambiguous initial staff definitions')
    available=set(ordered)
    require(set(requested)<=available,'unknown requested staff')
    measures=list(root.iter(NS+'measure'))
    require(measures,'no source measures')
    original_measure_ids=[m.get(ID) for m in measures]
    staff_subtrees={}
    edges=[]
    for m in measures:
        local=m.findall(NS+'staff')
        require({s.get('n') for s in local}==available and len(local)==len(available),
                'incomplete or duplicate whole-score staff storage')
        for staff in local:
            require(staff.get(ID),'staff identity missing')
            staff_subtrees[staff.get(ID)]=canonical(staff)
            for node in staff.iter():
                if not node.get('staff'):continue
                owners=set(node.get('staff').split())|{staff.get('n')}
                require(owners<=available,'unknown cross-staff destination')
                if len(owners)>1:edges.append((node.get(ID) or staff.get(ID),'cross_staff_storage',owners))

    controls=[]
    for measure in measures:
        for c in measure:
            if c.tag==NS+'staff':continue
            require(c.get(ID),'control identity missing')
            refs=[]
            for attr in ['startid','endid']:
                if c.get(attr):refs.append(c.get(attr))
            refs.extend(c.get('plist','').split())
            anchored=set()
            for ref in refs:
                require(ref.startswith('#') and len(ref)>1 and ' ' not in ref,'invalid control anchor')
                node=graph.nodes.get(ref[1:]);require(node is not None,'unresolved control anchor '+ref)
                anchored|=graph.owners(node)|{graph.ancestor(node,'staff').get('n')}
            explicit=set(c.get('staff','').split())
            require((anchored|explicit)<=available,'unknown control staff')
            owners=anchored|explicit
            require(owners or c.tag in GLOBAL_CONTROLS,'control ownership unresolved')
            # A shared dynamic's staff list is a set of separate applications.
            # Anchored relations, however, must never be split at a hidden row.
            if refs and len(owners)>1:edges.append((c.get(ID),'anchored_control',owners))
            require(c.tag not in GLOBAL_CONTROLS or not refs,'anchored global control needs explicit placement review')
            controls.append((measure,c,owners,refs))

    selected=set(requested);closure=[]
    while True:
        changed=False
        for ident,kind,owners in edges:
            added=owners-selected
            if added and selected&owners:
                closure.append({'id':ident,'kind':kind,'added_staff_numbers':sorted(added,key=int)})
                selected|=added;changed=True
        if not changed:break
    selected_order=[n for n in ordered if n in selected]
    contexts_before=_contexts(root)
    removed_controls=[];changes=[]
    for measure,c,owners,refs in controls:
        if c.tag in GLOBAL_CONTROLS:
            # Global text survives omission of the original top instrument.
            # Its sound and symbolic timing attributes remain unchanged.
            new_staff=' '.join(n for n in selected_order if n in owners) or selected_order[0]
        elif not owners&selected:
            removed_controls.append(c.get(ID));measure.remove(c);continue
        else:
            if refs:require(owners<=selected,'control was severed by row selection')
            new_staff=' '.join(n for n in selected_order if n in c.get('staff','').split())
        if c.get('staff') is not None and new_staff!=c.get('staff'):
            require(bool(new_staff),'retained control has empty display staff')
            changes.append({'id':c.get(ID),'tag':c.tag.removeprefix(NS),'old_staff':c.get('staff'),
                            'new_staff':new_staff,'reason':'global_placement' if c.tag in GLOBAL_CONTROLS else 'shared_staff_subset'})
            c.set('staff',new_staff)

    parents={c:p for p in root.iter() for c in p}
    for node in list(root.iter()):
        if node.tag in {NS+'staff',NS+'staffDef'} and node.get('n') not in selected:
            parents[node].remove(node)
    # Prune only now-empty groups; retain all labels/brackets of surviving groups.
    for node in reversed(list(root.iter(NS+'staffGrp'))):
        if not list(node.iter(NS+'staffDef')):parents[node].remove(node)

    output=serialize_mei(root);after=E.fromstring(output);after_graph=Ownership(after)
    require([m.get(ID) for m in after.iter(NS+'measure')]==original_measure_ids,'source measure sequence changed')
    retained=list(after.iter(NS+'staff'))
    require(len(retained)==len(measures)*len(selected),'stable staff count changed across measures')
    require(all(canonical(s)==staff_subtrees[s.get(ID)] for s in retained),'retained staff contents changed')
    contexts_after=_contexts(after)
    require(all(v==contexts_before[k] for k,v in contexts_after.items()),'retained effective notation context changed')
    for measure in after.iter(NS+'measure'):
        for c in measure:
            if c.tag==NS+'staff':continue
            refs=[c.get(a) for a in ['startid','endid'] if c.get(a)]+c.get('plist','').split()
            require(all(r[1:] in after_graph.nodes for r in refs),'retained control anchor missing')
    return {'mei':output,'source_mei_sha256':expected_mei_sha256,
        'projected_mei_sha256':hashlib.sha256(output).hexdigest(),
        'requested_staff_numbers':[n for n in ordered if n in requested],
        'selected_staff_numbers':selected_order,
        'added_context_staff_numbers':[n for n in selected_order if n not in requested],
        'structural_closure':closure,'display_control_changes':changes,
        'removed_control_ids':removed_controls,
        'retained_staff_subtrees_verified':len(retained),
        'retained_event_contexts_verified':len(contexts_after),
        'source_measures_preserved':len(measures),'layout_or_musical_acceptance':False}
