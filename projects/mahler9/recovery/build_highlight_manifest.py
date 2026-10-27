"""67 corroborated complete strand windows + explicit M3 pressure counterpoint.
Identity follows authored source membership. Color is never instrument/hash based.
"""
import json,gzip,pathlib,collections,fractions
B=pathlib.Path(__file__).parent;R=pathlib.Path('.');F=fractions.Fraction
shared=json.load(open(B/'palette-and-phrase-decisions.json'));A=json.load(open(B/'theme-phrases.json'));aps={p['phrase_id']:p for p in A['phrases']};all_events={};notes={};data={}
for m in range(1,5):
 d=json.load(open(f'work/score-sync-01/data/M{m}/data.json'));data[m]=d;notes[m]={n['id']:n for n in d['notes']}
 with gzip.open(d['events_ref']['path'],'rt') as f:
  for line in f:
   e=json.loads(line);all_events[m,e['event_id']]=e
context=json.load(open('work/revision-04/pedagogy/root-merge-09-working/motif/representative-instances.json'))['groups'];core={}
for g in context:
 for a in g['source_attached_groups']:
  for e in a['source_event_ids']:core[g['movement'],e]={'display_identity':'motif:'+g['family_id'],'slot':shared['local_motif_family_slots'][g['family_id']],'evidence':g['motif_instance_group_id']}
def q(e):return F(*e['absolute_onset_q'])
def end(e):return q(e)+F(*e['duration_q'])
def enrich(key,m,ids,slot,identity,*,evidence,whole=None,kind='independent_complete_strand',rationale='',peer=None):
 es=[all_events[m,e] for e in ids];es.sort(key=lambda e:(q(e),e['source_key']));voice={e['source_voice_id'] for e in es};assert len(voice)==1,(key,voice)
 qs=min(q(e) for e in es);qe=max(end(e) for e in es);first=es[0];last=max(es,key=end);real=[notes[m][e['event_id']] for e in es];v=next(iter(voice));all_scope=[e for (mm,_),e in all_events.items() if mm==m and e['source_voice_id']==v and qs<=q(e)<=max(q(x) for x in es)];selected={e['event_id'] for e in es};omitted=[e for e in all_scope if e['kind'] in ['pitched','unpitched'] and e['event_id'] not in selected]
 return {'span_id':key,'movement':m,'identity_id':identity,'identity_kind':kind,'whole_theme_id':whole,'local_motif_family_id':None,'palette_slot':slot,'color':shared['palette'][slot],'slot_rationale':rationale,'source_voice_id':v,'source_staff_ids':sorted({e['source_staff_id'] for e in es}),'raw_parts':sorted({e['xml_part_id'] for e in es}),'source_event_ids':[e['event_id'] for e in es],'source_keys':[e['source_key'] for e in es],'raw_measure_range':[min(e['raw_measure_index'] for e in es),max(e['raw_measure_index'] for e in es)],'source_from':{'raw_measure':first['raw_measure_index'],'quarter':first['onset_q'],'event_id':first['event_id']},'source_until':{'raw_measure':last['raw_measure_index'],'last_onset_quarter':last['onset_q'],'last_duration_q':last['duration_q'],'event_id':last['event_id']},'qrange_exact':[[qs.numerator,qs.denominator],[qe.numerator,qe.denominator]],'qrange':[float(qs),float(qe)],'local_sample_range':[min(n['range'][0] for n in real),max(n['range'][1] for n in real)],'evidence':evidence,'peer_correspondence':peer,'omitted_same_voice_nonrests':[{'event_id':e['event_id'],'source_key':e['source_key'],'reason':'not in this corroborated membership; may belong to adjacent strand, otherwise default pending actual score review'} for e in omitted],'rest_event_ids':[e['event_id'] for e in all_scope if e['kind']=='rest'],'qa_render_eligible':True,'production_visual_approved':False,'native_full_phrase_review':{'A':'pending','B':'pending','C':'pending'}}
spans=[];links=[]
primary_ids={'CONS-1-298f28206c46','CONS-1-48fcb066b1a2','CONS-1-3613bb8a2f5d'}
for p in shared['phrase_candidates']:
 aid=min((aps[x] for x in p['A_refs']),key=lambda a:len(a['source_event_ids']));m=p['movement'];lo,hi=p['raw_measure_range'];part=p['parts'][0];slot=aid['palette_slot'];why='Authored independent phrase role; not a claim of whole-theme identity.';identity='strand:'+p['id'];whole=None
 if p['id'] in primary_ids:slot='purple';identity='whole:M1-primary-song';whole='M1-primary-song';why='Triad source/narrative agreement: first song, continuation and return keep purple across second/first violins.'
 if p.get('whole_theme_id')=='M2-landler-theme':slot='purple';identity='whole:M2-landler-theme';whole='M2-landler-theme';why='Exact20pair source equality and authored four-bar reprise; same purple across violin and bassoon.'
 if m==1 and lo in [174,191] and part=='P30':slot='ochre';why='Sustained/high anger foreground distinct from simultaneous green descending/counter materials; independent strand identity.'
 if m==1 and part=='P14' and 234<=lo<=242:slot='green';why='Weighted descending brass strand, harmonizes accepted chromatic descent identity without asserting full-theme equality.'
 if m==1 and part=='P14' and 412<=lo<=416:slot='green';why='Explicit late chromatic line keeps green; other coda material stays independently identified.'
 if m==4 and part=='P25' and lo>=3 and hi<=147:slot='green';why='Turn-bearing principal adagio strand uses persistent green, including returns; local turn core already green.'
 if m==4 and part=='P25' and lo<=2:slot='purple';why='Bare initial descending utterance is a distinct strand from later turn-bearing statements; accepted adagio_descent core purple.'
 if m==4 and lo>=148:slot='purple';why='Late isolated/final-memory strand, not automatically merged into the full turn theme.'
 ids=list(p['source_event_ids']);added=[]
 closures={'CONS-1-298f28206c46':('urn:uuid:1933a168-9b7b-4198-a711-474a7dee01c0','z1meytkv'),'CONS-1-c491f541cdc1':('urn:uuid:a87e6e81-4d51-49ab-8cef-6640723a6dd8','yuqs6c2'),'CONS-3-e51282324361':('urn:uuid:96e06c6e-1710-4813-afb0-2bc68e56a3e6','qh9ur9j')}
 if p['id'] in closures:
  target,control=closures[p['id']]
  assert all_events[m,target]['source_voice_id']==all_events[m,ids[0]]['source_voice_id']
  ids.append(target)
  links.append({'relation':'explicit_slur_closure','span_id':p['id'],'added_target_uuid':target,'source_control_id':control,'evidence':'A/B actual complete native crop and independent MEI/source q/voice validation; target only, not entire next measure'})

 if p['id'] in ['CONS-3-83183528d926','CONS-3-e35fe525d3d2']:
  voice=all_events[m,ids[0]]['source_voice_id']
  added=[e['event_id'] for (mm,_),e in all_events.items() if mm==3 and e['xml_part_id']==part and e['source_voice_id']==voice and e['raw_measure_index']==8 and e['kind']=='pitched']
  ids=list(dict.fromkeys(added+ids))
 s=enrich(p['id'],m,ids,slot,identity,evidence=p['evidence'],whole=whole,rationale=why,peer={'A':p['A_refs'],'B':p['B_ref'],'C':p['C_ref'],'boundary_agreement':p['boundary_agreement']})
 if added:s['membership_correction']={'original_corrob_event_ids':p['source_event_ids'],'added_source_event_ids':added,'reason':'Actual MXL raw8 contains omitted main/counterline opening; printed/raw translation in original independent drafts started one measure late. A independently checked source pitch/duration; C identified main prototype raw8; B source review requested.','crop_context_raw_from':7}
 spans.append(s)
# Actual complete native crop review: preserve distinct source voices, explicitly
# link the grace lead-in to its MEI slur target in the next source layer.
short_ids={'CONS-2-04e86b770d77','CONS-3-50e6934a12e6','CONS-3-618762daab74','CONS-4-fd8c3d1d0713'}
for s in spans:
 if s['span_id'] in short_ids:
  s['identity_kind']='local_material_strand'
  s['review_caution']='Actual native crop shows a short independent local voice, not a whole musical phrase.'
target='urn:uuid:9981711f-a133-402a-b5ab-1dcd00636ada'
s=enrich('QA-M2-P27-R153-SLUR-TARGET',2,[target],'green','strand:CONS-2-04e86b770d77:target',kind='local_material_strand',evidence=['canonical/M2/normalized.mei#a1fdmso5: raw152/staff44/layer2 grace start to raw153/staff44/layer1 target','A actual native crop28 and raw source UUID/q/duration/recording interval audit'],rationale='Explicit native slur landing belongs to the same visible grace-led gesture; source voice changes, so retain a separate source strand, same green slot.')
s['notational_continuation_of']='CONS-2-04e86b770d77'
spans.append(s)
links.append({'relation':'explicit_notational_continuation','from_span':'CONS-2-04e86b770d77','to_span':s['span_id'],'source_control_id':'a1fdmso5','source_voice_changes':True,'target_uuid':target,'target_qrange':[454,455],'target_local_samples':[24239040,24273600],'whole_theme_identity_claim':False})
# Pressure QA: four explicit complete source-voice windows, not instrument colors.
# Lower line D(long3),E,F,G,F,E is thematic driving line; upper A,G,F,E,D,B differs.
pressure=[]
for part,lo,hi,slot,material in [('P19',523,537,'purple','M3-return-driving-line'),('P35',523,532,'purple','M3-return-driving-line'),('P31',523,532,'green','M3-return-upper-counterline'),('P32',523,532,'green','M3-return-upper-counterline')]:
 es=[e for (m,_),e in all_events.items() if m==3 and e['xml_part_id']==part and lo<=e['raw_measure_index']<=hi and e['kind'] in ['pitched','unpitched']]
 voices=collections.defaultdict(list)
 for e in es:voices[e['source_voice_id']].append(e)
 # Dedicated source voice is explicit in output; other voices remain default.
 voice,es=max(voices.items(),key=lambda x:len(x[1]));key=f'PRESSURE-M3-{part}-R{lo}-{hi}'
 s=enrich(key,3,[e['event_id'] for e in es],slot,'strand:'+material+':'+part,evidence=['work/revision-04/pedagogy/root-merge-09-working/teaching/teaching-path.json#MP-M3-U15','actual MXL source pitch/onset/duration examined raw523–526; native complete crop still to review'],kind='supplemental_pressure_complete_voice_candidate',rationale='Explicit lower thematic driving line purple versus simultaneous upper counterline green; exact membership only, no instrument-wide rule.');s['material_candidate']=material;s['review_caution']='First-cell relation observed; complete-window phrase end/cadence and later divergence need actual native crop.';spans.append(s);pressure.append(key)
# Compile one visible identity per event. Core is an authored higher display layer.
claims=collections.defaultdict(list)
for s in spans:
 for e in s['source_event_ids']:claims[s['movement'],e].append(s)
display={};overlaps=[]
for (m,e),cs in claims.items():
 ordered=sorted(cs,key=lambda s:(-len(s['source_event_ids']),s['span_id']));slots={s['palette_slot'] for s in cs};winner=ordered[0]
 if len(slots)>1:
  # Explicitly record ambiguity, choose conservative main unless accepted local core fixes it.
  chosen={'identity_id':'default:unresolved-strand-overlap','palette_slot':'main','color':shared['palette']['main'],'source':'explicit conflicting strand slots; requires native score adjudication'}
 else:chosen={'identity_id':winner['identity_id'],'palette_slot':winner['palette_slot'],'color':winner['color'],'source':winner['span_id']}
 c=core.get((m,e))
 if c:chosen={'identity_id':c['display_identity'],'palette_slot':c['slot'],'color':shared['palette'][c['slot']],'source':c['evidence']}
 if len(cs)>1 or c:
  overlaps.append({'movement':m,'event_id':e,'strand_ids':[s['span_id'] for s in cs],'strand_slots':sorted(slots),'local_core':c,'chosen':chosen,'decision':'One fixed display identity; accepted local family wins over strand layer; same-slot duplicate windows keep widest context and retain other IDs as metadata. Different-slot strand conflicts default main pending explicit review.'})
 display[f'M{m}/{e}']=chosen
# Core outside windows still colored with same frozen family slot, not forgotten.
for (m,e),c in core.items():display.setdefault(f'M{m}/{e}',{'identity_id':c['display_identity'],'palette_slot':c['slot'],'color':shared['palette'][c['slot']],'source':c['evidence']})
notes_out={f'M{m}/{e}':{**all_events[m,e],'recording_range':notes[m][e]['range'],'display_staff':notes[m][e]['staff'],'storage_staff':notes[m][e]['storage_staff']} for m,e in claims}
out={'schema':'score-sync-02-highlight-strands-1','status':'67 complete corroborated strand windows ready for actual native score QA; whole-theme relation only when separately supported','palette':shared['palette'],'local_family_slots':shared['local_motif_family_slots'],'default_color':shared['palette']['main'],'strands':spans,'notational_continuation_links':links,'known_identity_links':[{'identity_id':'M3-return-driving-line','relation':'variant, not exact whole-phrase transposition: original P31raw8–9 to lowerP19raw523–524 first7notes -7semitones with same durations; eighth differs; P19/P35 diverge rhythm fromraw525','evidence':'A/C independent actual MXL pitch/duration comparison; full crop pending'},{'identity_id':'whole:M1-primary-song','spans':sorted(primary_ids),'relation':'first theme continuation and return; triad narrative/source supported, native crop pending'},{'identity_id':'whole:M2-landler-theme','spans':[s['span_id'] for s in spans if s['whole_theme_id']=='M2-landler-theme'],'relation':'exact20note paired return across instrument; no stronger whole-work relation implied'}],'pressure_supplement_ids':pressure,'display_event_map':display,'overlap_decisions':overlaps,'source_event_records':notes_out,'summary':{'corroborated_full_strands':67,'explicit_continuation_strands':1,'pressure_supplement_strands':len(pressure),'full_strand_unique_events':len(claims),'all_display_events_including_core':len(display),'different_slot_strand_conflicts':sum(len(x['strand_slots'])>1 for x in overlaps),'production_visual_approved':0},'hard_limits':['Source membership and strand color are explicit; no all-part/all-staff color assignment.','Independent strand IDs can share slot without claiming same theme.','Do not call source/numeric agreement native visual approval.','67strands do not cover every possible full musical statement in92units; gaps remain explicit default main and need further musical review.']}
json.dump(out,open(B/'highlight-strands.json','w'),ensure_ascii=False,indent=2);print(out['summary'])
