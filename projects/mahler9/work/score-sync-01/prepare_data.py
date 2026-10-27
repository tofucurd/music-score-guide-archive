"""Extract full-recording data; no teaching layers or excerpt edits survive."""
from pathlib import Path
from fractions import Fraction as Q
import json, gzip, hashlib
from core import continuous_ranges, sounding_cohort, interpolate, source_sample

W = Path(__file__).resolve().parent
R = W.parents[1]
L = R / 'work/revision-04/engineering/root-integration-working-01'
E = R / 'work/revision-04/engineering/root-source-han-routing-working-01'

def load(p): return json.loads(p.read_text())
def dump(p, x): p.write_text(json.dumps(x, ensure_ascii=False, separators=(',', ':')) + '\n')
def ref(p):
    b = p.read_bytes()
    return dict(path=str(p.relative_to(R)), bytes=len(b), sha256=hashlib.sha256(b).hexdigest())

def main():
    clock_path = R / 'work/revision-04/alignment/full-display-merge-01/display-clock.json'
    clock = load(clock_path)
    index = load(L / 'native-unit-geometry-index-02.json')
    movements = []
    for m in range(1, 5):
        out = W / f'data/M{m}'; out.mkdir(parents=True, exist_ok=True)
        pkg = load(E / f'entry-navigation-bound-15/M{m}/package.json')
        source, = pkg['layers']['audio']['payload']['sources']
        full_map = next(mp for mp in clock['maps'] if mp['source_id'] == source['id'])
        points = [[p['sample'], float(Q(*p['position']))] for p in full_map['points']]
        assert points[0][0] == 0 and points[-1][0] == source['output_count']
        assert all(b[0] > a[0] and b[1] >= a[1] for a,b in zip(points,points[1:]))
        layout = next(x for x in index['layouts'] if x['unit_id'] == f'MP-M{m}-U01' and x['layout_mode'] == 'main')
        bindings = load(R / layout['source_bindings']['path'])
        bind = {b['event_id']: b for b in bindings['storage_bindings']}
        events_path = R / f'work/revision-04/alignment/score-inputs-02/movement-{m}-events.jsonl.gz'
        with gzip.open(events_path, 'rt') as f: records = [json.loads(line) for line in f]
        timing = {e['event_id']:e for k in ['highlights','unpitched_ledger','nonprinting_ledger'] for e in clock[k] if e.get('movement') == m}
        notes, missing, extended = [], [], []
        for e in records:
            if not e['is_player'] or e['kind'] not in ('pitched','unpitched'): continue
            b = bind.get(e['event_id']); t = timing.get(e['event_id'])
            if not b:
                missing.append(e['event_id']); continue
            q=float(Q(*e['absolute_onset_q'])); duration=float(Q(*e['duration_q']))
            if t:
                interval = t.get('display_range') or t.get('range') or t.get('highlight_range')
                basis='existing_recording_aligned_display_interval'
            else:
                interval = [source_sample(points,q,onset=True),source_sample(points,q+duration)]
                if e['is_grace']:
                    # New grace heads are linked to their principal's recording clock,
                    # never called measured attacks. Reserve a brief pre-principal window.
                    interval=[max(0,interval[0]-4800),interval[0]]
                basis='full_source_note_projected_through_existing_Walter_clock'
                extended.append(e['event_id'])
                t={}
            assert interval is not None, e['event_id']
            assert interval[1]>=interval[0], (e['event_id'],interval)
            notes.append(dict(id=e['event_id'], engraver_id=b['engraver_id'],
                staff=b['mei_display_staff_n'], storage_staff=b['mei_ancestor_staff_n'],
                measure=e['raw_measure_index'], q=float(Q(*e['absolute_onset_q'])),
                duration=duration, range=interval, grace=e['is_grace'],clock_basis=basis,
                kind=e['kind'], visible=b['render_visibility']=='visible',
                tie_start=t.get('is_tie_start',any(x['type']=='start' for x in e['ties'])),
                tie_stop=t.get('is_tie_stop',any(x['type']=='stop' for x in e['ties']))))
        assert not missing, ('missing full-source note data',m,missing[:15],len(missing))
        # Every raw measure retains its full-source position regardless of staff omission.
        measures = {}
        for e in records:
            if not e['is_player']: continue
            raw = e['raw_measure_index']; q=float(Q(*e['absolute_onset_q'])-Q(*e['onset_q']))
            end=float(Q(*e['absolute_onset_q'])+Q(*e['duration_q']))
            if raw not in measures: measures[raw] = dict(raw=raw,q=q,end=end)
            else:
                assert measures[raw]['q']==q
                measures[raw]['end']=max(measures[raw]['end'],end)
        rows = []
        units = sorted((u for u in clock['units'] if u['movement']==m),key=lambda u:u['source_range'][0])
        assert units[0]['source_range'][0] == 0 and units[-1]['source_range'][1] == source['output_count']
        assert all(a['source_range'][1] == b['source_range'][0] for a,b in zip(units,units[1:]))
        for unit in units:
            a,b = unit['source_range']; qa,qb = interpolate(points,a),interpolate(points,b)
            active = sounding_cohort(notes, [a,b])
            # Retain storage rows as well for real cross-staff engravings.
            storage = {e['storage_staff'] for e in notes if e['staff'] in active and
                       e['range'][0]<b and (e['range'][1]>a or a<=e['range'][0]==e['range'][1])}
            ms = [m for m in measures.values() if m['q']<qb and m['end']>qa]
            assert active and ms, unit['unit_id']
            rows.append(dict(id=unit['unit_id'],movement=m,range=[a,b],qrange=[qa,qb],
                requested_staves=sorted(active|storage,key=int),sounding_staves=sorted(active,key=int),
                raw_measures=[min(x['raw'] for x in ms),max(x['raw'] for x in ms)]))
        nav, = pkg['layers']['teaching']['payload']['navigation']['domains']
        assert nav['range'] == [0,source['output_count']]
        data = dict(movement=m,source=source,mei=layout['source_mei'],bindings=layout['source_bindings'],
                    clock=points,nav=nav,sections=rows,notes=notes,measures=list(measures.values()),
                    clock_ref=ref(clock_path),events_ref=ref(events_path),extended_note_ids=extended,
                    grid=[dict(id=bind[e['event_id']]['engraver_id'],q=float(Q(*e['absolute_onset_q'])),
                               measure=e['raw_measure_index'],kind=e['kind'],grace=e['is_grace'])
                          for e in records if e['is_player'] and e['event_id'] in bind
                          and bind[e['event_id']]['render_visibility']=='visible'])
        dump(out/'data.json',data)
        movements.append(dict(movement=m,count=source['output_count'],data=ref(out/'data.json'),
                              sections=len(rows),notes=len(notes)))
        print(json.dumps(dict(movement=m,sections=len(rows),notes=len(notes),
                              staves=[len(x['requested_staves']) for x in rows])),flush=True)
    ranges = continuous_ranges([m['count'] for m in movements])
    for m,r in zip(movements,ranges): m['global_range']=r
    dump(W/'timeline.json',dict(sample_rate=96000,fps=60,movements=movements,
        total_samples=ranges[-1][1],total_frames=(ranges[-1][1]+1599)//1600,
        audio_policy='sequential full source samples exactly once, no inserted padding between movements',
        max_video_tail_padding_samples=1599,commentary=False,pedagogical_annotations=False,
        source_clock_acoustic_precision_not_individually_verified=True))

if __name__ == '__main__': main()
