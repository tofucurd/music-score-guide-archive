"""Preserve source trill marks despite five zero-extent MusicXML ornaments.

The original XML explicitly starts and stops each wavy line on the same note.
Its MEI conversion asks for an extender ending at the starting beat, which
Verovio rejects along with the trill mark. Keep the original trill mark and
remove only this invalid zero-length display extender; do not invent a span.
"""
import xml.etree.ElementTree as X
import gzip,json,sys,zipfile,re
from fractions import Fraction
from pathlib import Path
import os
from prepare_data import L,R
sys.path.insert(0,str(L))
from mei_serialization import serialize_mei
NS='{http://www.music-encoding.org/ns/mei}'
ID='{http://www.w3.org/XML/1998/namespace}id'
TARGETS={2:{'y13xprlx','huztrgx','c1t3gvdy','rowtjds','h1mbwbo0'},
         3:{'y1d9fi9z','rihzzv0','yrpg2hc','tfn0d6b','b19jezyn','y8cdv74','i1p59krc','z1klch00'}}

def repair(mei,movement):
    if movement==1:
        root=X.fromstring(mei);ids={e.get(ID):e for e in root.iter() if e.get(ID)}
        if 's1lyjxwb' not in ids:return mei,[]
        outer=ids['s1lyjxwb'];parents={c:p for p in root.iter() for c in p};layer=parents[outer]
        assert outer.get('num')=='3' and outer.get('numbase')=='2'
        assert [e.tag.removeprefix(NS) for e in outer]==['rest','rest','beam','beam','beam','beam']
        # Original XML closes both tuplets on note 5, then starts independent
        # eighth-note triplets. The importer left the outer tuplet open.
        src=Path(os.environ['MAHLER9_M1_MXL'])
        with zipfile.ZipFile(src) as z:xml=X.fromstring(z.read('score.xml'))
        part=next(p for p in xml.findall('part') if p.get('id')=='P20')
        notes=part.findall('measure')[171].findall('note')
        assert [(n.get('type'),n.get('number')) for n in notes[4].findall('notations/tuplet')]==[('stop','1'),('stop','2')]
        assert all(n.findtext('time-modification/actual-notes')=='3' and n.findtext('time-modification/normal-notes')=='2' for n in notes[5:])
        tail=list(outer)[3:];position=list(layer).index(outer)+1
        for i,node in enumerate(tail):outer.remove(node);layer.insert(position+i,node)
        # Verovio uses the nearest tuplet ratio, without multiplying its parent.
        # Give the inner three sixteenths their source's cumulative 9:4 ratio.
        # repair_svg restores the source's printed inner digit 3 afterwards.
        inner=ids['ywj7d8v'];inner.set('num','9');inner.set('numbase','4')
        return serialize_mei(root),[dict(id='s1lyjxwb',source=str(src),part='P20',raw_measure=172,
            moved_beams=[n.get(ID) for n in tail],inner_effective_ratio=[9,4],inner_printed_digit=3,
            reason='honor source tuplet stops and cumulative inner duration; note contents unchanged')]
    if movement not in TARGETS:return mei,[]
    root=X.fromstring(mei);ids={e.get(ID):e for e in root.iter() if e.get(ID)};changes=[]
    with gzip.open(R/f'work/revision-04/alignment/score-inputs-02/movement-{movement}-events.jsonl.gz','rt') as f:
        records={'r04_'+e['event_id'].removeprefix('urn:uuid:').replace('-',''):e for e in map(json.loads,f)}
    for tid in TARGETS[movement]:
        trill=ids.get(tid)
        if trill is None:continue
        anchor=ids[trill.get('startid')[1:]]
        note=anchor if anchor.tag==NS+'note' else next(anchor.iter(NS+'note'))
        evidence=records[note.get(ID)];notation=X.fromstring(evidence['notations_xml'])
        waves=notation.findall('ornaments/wavy-line')
        assert [w.get('type') for w in waves]==['start','stop']
        assert notation.find('ornaments/trill-mark') is not None
        assert trill.get('tstamp2')=='0m+1' and evidence['onset_q']==[0,1]
        old=dict(trill.attrib);trill.attrib.pop('tstamp2');trill.set('extender','false')
        changes.append(dict(id=tid,source_key=evidence['source_key'],before=old,after=dict(trill.attrib),
            reason='same-note start and stop have no nonzero wavy span; retain original trill glyph'))
    if movement==3 and 'fynmqpb' in ids:
        # Source XML encodes voices serially: the stop in voice 1 at q=4
        # precedes the start in voice 3 at q=3 in document order. Recover the
        # musical order from durations/backups, rather than inventing an end.
        src=Path(os.environ['MAHLER9_M3_MXL'])
        with zipfile.ZipFile(src) as z:xml=X.fromstring(z.read('score.xml'))
        part=next(p for p in xml.findall('part') if p.get('id')=='P2')
        divisions=None;beat_type=None
        for measure in part.findall('measure')[:655]:
            if measure.find('attributes/divisions') is not None:divisions=int(measure.findtext('attributes/divisions'))
            if measure.find('attributes/time/beat-type') is not None:beat_type=int(measure.findtext('attributes/time/beat-type'))
        q=Fraction(0);events=[]
        for node in part.findall('measure')[654]:
            if node.tag=='note' and node.find('chord') is None and node.find('grace') is None:
                q+=Fraction(int(node.findtext('duration')),divisions)
            elif node.tag in ('backup','forward'):
                q+=Fraction(int(node.findtext('duration')),divisions)*(1 if node.tag=='forward' else -1)
            elif node.tag=='direction':
                shift=node.find('direction-type/octave-shift')
                if shift is not None:
                    assert node.findtext('staff')=='1' and shift.get('size')=='8' and shift.get('number')=='1'
                    events.append((shift.get('type'),q))
        assert events==[('stop',Fraction(4)),('down',Fraction(3))] and beat_type==2
        octave=ids['fynmqpb'];old=dict(octave.attrib)
        assert not octave.get('endid') and not octave.get('tstamp2')
        octave.set('tstamp2','0m+3')
        changes.append(dict(id='fynmqpb',before=old,after=dict(octave.attrib),
            source_chronology_q=dict(start=3,stop=4,beat_type=2),
            source=str(src),reason='recover explicit XML octave stop at q4 after voice-backup reordering'))
    return serialize_mei(root),changes

def repair_svg(svg,movement):
    if movement!=1 or b'id="ywj7d8v"' not in svg:return svg
    pattern=rb'(id="ywj7d8v" class="tuplet">\s*<g[^>]+class="tupletNum">\s*<use xlink:href="#)E889(-[^\"]+)'
    match=re.search(pattern,svg)
    assert match,'Expected the normalized inner tuplet numeral'
    assert b'id="E883'+match.group(2)+b'"' in svg,'Native triplet digit must exist in definitions'
    fixed,count=re.subn(pattern,rb'\g<1>E883\g<2>',svg,count=1)
    assert count==1
    return fixed
