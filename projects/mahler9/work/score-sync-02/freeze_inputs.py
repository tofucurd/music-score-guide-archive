"""Freeze all runtime source assets, not mutable job status or review metadata."""
from pathlib import Path
import hashlib,json,subprocess
from runtime_environment import runtime_environment
W=Path(__file__).resolve().parent;R=W.parents[1]
def digest(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  while b:=f.read(4*1024*1024):h.update(b)
 return h.hexdigest()
def main():
 files=set(W.glob('*.py'))|set(W.glob('*.mjs'))|set((W/'assets').glob('*.json'))
 for m in range(1,5):
  c=W/f'canonical/M{m}'
  files.update(c.glob('*.svg'));files.update(c.glob('*.css'));files.update(c.glob('*.mei'));files.update(c.glob('measures/*.svg'))
  files.update([c/'source.json',c/'geometry-ink-final.json',R/f'work/score-sync-01/data/M{m}/data.json'])
 files.update((R/'work/score-sync-01/fonts').glob('*.ttf'))
 for s in ['work/score-sync-01/timeline.json','work/score-sync-01/scroll_renderer.py','work/score-sync-01/prepare_data.py','work/score-sync-01/core.py','work/score-sync-01/audio/manifest.json','work/score-sync-01/audio/Walter-full-96k24.m4a','work/revision-04/engineering/root-source-han-routing-working-01/src/cdp-transport.mjs','work/revision-04/assets/fonts/source-han-official-01/SourceHanSerifSC-Regular.otf','work/revision-04/engineering/root-integration-working-01/score-text-fonts-working-01/Leland.otf']:
  files.add(R/s)
 rows=[dict(path=str(p.relative_to(R)),bytes=p.stat().st_size,sha256=digest(p)) for p in sorted(files)]
 result=dict(schema='score-sync-native-frozen-02',scene_module='scene_noteink_stroke.mjs',files=rows,video=dict(codec='hevc',profile='Main 4:4:4 10',width=3840,height=2160,fps=60,pixel_format='yuv444p10le',preset='medium',crf=16,max_bitrate=16000000,buffer_size=32000000,chroma_qp_offsets=[-8,-8],cursor_layer='behind native score glyphs',native_notehead_shape='unchanged'),audio=dict(policy='copy immutable continuous original96k24 ALAC',sample_rate=96000,bits=24,channels=2),environment=runtime_environment())
 (W/'render-inputs.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
 print('Frozen',len(rows),'files',sum(r['bytes'] for r in rows),'bytes',digest(W/'render-inputs.json'))
if __name__=='__main__':main()
