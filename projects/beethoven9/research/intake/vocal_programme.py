"""Attach full-source vocal presentation to native project scenes.

Window selection only omits complete, inactive global cohorts. It never fits
lyrics, changes grouping, or constructs a layout from the output chunk.
"""
from __future__ import annotations
import base64
import copy
import hashlib
import io
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(path):
    return json.loads(Path(path).read_text())


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_digest(value):
    data = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(data.encode()).hexdigest()


def validate_sources(timeline, schedule):
    for record in timeline['source_hashes'].values():
        if digest(ROOT / record['path']) != record['sha256']:
            raise ValueError('Vocal source changed: ' + record['path'])
    expected = schedule['compile_inputs']
    for name, value in [('full_timeline', timeline), ('panel_entries', schedule['panel_entries']),
                        ('panel_presence', schedule['panel_presence'])]:
        if source_digest(value) != expected[name]:
            raise ValueError('Vocal schedule/input mismatch: ' + name)


def full_font_css(native_css, timeline):
    """Retain every already-embedded native character and add all vocal text."""
    from fontTools.ttLib import TTFont
    from score_sync.visual import font_css
    chars = set()
    for encoded in re.findall(r'base64,([A-Za-z0-9+/=]+)', native_css):
        with TTFont(io.BytesIO(base64.b64decode(encoded))) as font:
            chars.update(chr(cp) for table in font['cmap'].tables if table.isUnicode() for cp in table.cmap)
    for lane in timeline['lanes']:
        chars.update(lane['label'])
        for phrase in lane['phrases']:
            chars.update(phrase['de'])
            chars.update(phrase['zh'])
    chars.update('、0123456789')
    alphabet = ''.join(sorted(chars))
    font_paths = [Path(__import__('os').environ['SCORE_SYNC_ENGINE']) / 'assets/fonts' / f'SourceHanSerifSC-{w}.otf'
                  for w in ('Light', 'Regular', 'Medium')]
    key = source_digest({'alphabet': alphabet, 'font_files': [digest(p) for p in font_paths]})
    cache = ROOT / 'research/vocal-production-integration/font-cache'
    cache.mkdir(parents=True, exist_ok=True)
    path = cache / (key + '.css')
    if not path.exists():
        path.write_text(font_css(alphabet))
    return path.read_text()


def prepare_spec(spec, mode='video', *, schedule_path=None, layout_path=None):
    """Mutate only derived scene specs, leaving the canonical score/clock intact."""
    if mode == 'cover':
        return []
    scenes = spec.get('scenes', [spec])
    targets = [(i, scene) for i, scene in enumerate(scenes) if scene.get('movement_label') == '第四乐章']
    if not targets:
        return []
    timeline = read(ROOT / 'content/vocals/timeline.json')
    source_schedule = Path(schedule_path or ROOT / 'content/vocals/cohort-schedule.json')
    schedule = read(source_schedule)
    layout = read(layout_path or source_schedule.with_name('layout-schedule.json'))
    validate_sources(timeline, schedule)
    if 'compile_inputs' in layout:
        if layout['compile_inputs']['cohort_schedule'] != source_digest(schedule):
            raise ValueError('Vocal geometry was compiled for another cohort schedule')
        if layout['compile_inputs']['full_timeline'] != source_digest(timeline):
            raise ValueError('Vocal geometry was compiled for another lyric timeline')
    elif schedule_path is None:
        raise ValueError('Published vocal geometry requires source bindings')
    if {c['id'] for c in layout['cohorts']} != {c['id'] for c in schedule['cohorts']}:
        raise ValueError('Vocal layout/cohort identities differ')
    voice_ids = {lane['id'] for lane in timeline['lanes']}
    results = []
    for index, scene in targets:
        # A derived spec can be reused for another window. Never retain a prior
        # window's vocal payload when the new one contains no vocal material.
        scene.pop('vocalProgramme', None)
        scene.pop('vocal_note_staves', None)
        states = []
        for frame in spec['frames']:
            if 'actors' in frame:
                states.extend(actor['state'] for actor in frame['actors'] if actor['scene'] == index)
            elif index == 0:
                states.append(frame)
        if not states:
            continue
        start = min(state['seconds'] for state in states)
        end = max(state['seconds'] for state in states) + 1 / spec.get('fps', 60)
        selected = [c for c in schedule['cohorts'] if c['display_start'] < end and c['display_end'] > start]
        # A short bridge can outlive the outgoing words. Retain both complete
        # layouts as context until the incoming body has settled, without
        # extending any phrase's own source visibility envelope.
        bridge_ids = {cid for h in schedule['handoffs']
                      if h['boundary'] < end and h.get('settle_end', h['boundary'] + .45) > start
                      for cid in (h['from_cohort'], h['to_cohort'])}
        selected_ids = {c['id'] for c in selected} | bridge_ids
        selected = [c for c in schedule['cohorts'] if c['id'] in selected_ids]
        panel_present = any(w['enter_start'] < end and w['exit_end'] > start
                            for w in schedule['panel_presence']['windows'])
        if not selected and not panel_present:
            continue
        ids = {c['id'] for c in selected}
        local_schedule = {**schedule, 'cohorts': copy.deepcopy(selected),
                          'handoffs': [copy.deepcopy(h) for h in schedule['handoffs']
                                       if h['from_cohort'] in ids or h['to_cohort'] in ids]}
        scene['vocalProgramme'] = {'timeline': timeline, 'schedule': local_schedule,
                                  'layout': {**layout, 'cohorts': [copy.deepcopy(c) for c in layout['cohorts'] if c['id'] in ids]}}
        scene['vocal_note_staves'] = {n['id']: n['staff'] for n in scene['geometry']['notes'] if n['staff'] in voice_ids}
        scene['fonts'] = full_font_css(scene['fonts'], timeline)
        results.append({'scene': index, 'seconds': [start, end], 'cohort_ids': sorted(ids),
                        'canonical_cohorts_unmodified': all(c == next(s for s in schedule['cohorts'] if s['id'] == c['id'])
                                                           for c in local_schedule['cohorts'])})
    return results
