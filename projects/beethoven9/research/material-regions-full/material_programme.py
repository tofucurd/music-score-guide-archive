"""Attach reviewed musical-material spans to derived scenes only.

The source score, clock, production activity colours and vocal programme remain
unchanged. All persisted inputs are checked against the registry before use.
"""
from pathlib import Path
import hashlib
import json
from functools import lru_cache

ROOT = Path(__file__).resolve().parents[2]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


@lru_cache(maxsize=16)
def _load(path, size, mtime_ns):
    # Size/mtime are part of the key, not accepted as content authentication.
    return json.loads(Path(path).read_text())


def read(path):
    p=Path(path);s=p.stat()
    return _load(str(p),s.st_size,s.st_mtime_ns)


def prepare_spec(spec, mode='video', *, registry_path=None):
    if mode=='cover':
        return []
    path=Path(registry_path or ROOT/'content/material-regions/index.json')
    registry=read(path)
    if registry.get('style')!='native-material-regions-v2':
        raise ValueError('Material registry must use the selected v2 style')
    palette_binding=registry['presentation_palette']
    palette_path=ROOT/palette_binding['path']
    if digest(palette_path)!=palette_binding['sha256']:
        raise ValueError('Material presentation palette changed')
    presentation=read(palette_path)
    table={m['movement_label']:m for m in registry['movements']}
    results=[]
    for i,scene in enumerate(spec.get('scenes',[spec])):
        scene.pop('material_regions',None)
        entry=table.get(scene.get('movement_label'))
        if not entry:
            raise ValueError('Scene is not covered by the four-movement material registry')
        source=ROOT/entry['path']
        if digest(source)!=entry['sha256']:
            raise ValueError('Material map changed: '+str(source))
        data=read(source)
        for name,expected in entry['source_bindings'].items():
            if digest(ROOT/name)!=expected:
                raise ValueError('Material source changed: '+name)
        geo=read(ROOT/f".score-sync/{entry['id']}/geometry.json")
        if scene['geometry']['notes']!=geo['notes']:
            raise ValueError('Material mapping belongs to a different native geometry')
        payload={k:data[k] for k in ('regions','assignments','palette','short_names')}
        roles=presentation['movements'][entry['id']]
        if set(roles)!=set(data['palette']):
            raise ValueError('Presentation palette does not cover the source materials')
        payload['palette']={theme:presentation['roles'][role] for theme,role in roles.items()}
        payload['palette_revision']=presentation['revision']
        payload['shared_staff_neutral_intervals']=data.get('shared_staff_neutral_intervals',[])
        payload['vocal_phrase_themes']=data.get('vocal_phrase_themes',[])
        payload['x_shift']=data.get('x_shift',240)
        scene['material_regions']=payload
        # The original badge labels already occur in the full vocal font set.
        # Additional theme names are explicitly added without system-font fallback.
        if payload['vocal_phrase_themes']:
            from vocal_programme import full_font_css
            scene['fonts']=full_font_css(scene['fonts'],{'lanes':[
                {'label':''.join(payload['short_names'].values()),'phrases':[]}]})
        results.append({'scene':i,'movement':entry['id'],
                        'palette_revision':presentation['revision'],
                        'palette_sha256':palette_binding['sha256'],
                        'regions':len(payload['regions']),'assigned_notes':len(payload['assignments'])})
    return results
