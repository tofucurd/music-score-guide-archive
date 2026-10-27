from pathlib import Path
import sys,json
import os
ROOT=Path(__file__).resolve().parents[1]
VENDOR=Path(os.environ.get('SCORE_SYNC_VENDOR',str(ROOT.parents[1]/'vendor/score-sync-video')))
sys.path.insert(0,str(VENDOR/'scripts'))
from score_sync import visual,workflow
cfg=workflow.load_project(ROOT/'project.json');b=visual.bundle(cfg,ROOT/'.score-sync/m1')
state=visual.frame_state(b,b['time_at'](266.08))
words={'composer_en':'LUDWIG VAN BEETHOVEN','composer_zh':'贝多芬','performer_zh':'库伦齐斯指挥','ensemble_zh':'musicAeterna 乐团','performer_en':'TEODOR CURRENTZIS','ensemble_en':'MUSICAETERNA'}
corpus=json.dumps(cfg,ensure_ascii=False)+json.dumps(b['geometry']['staves'],ensure_ascii=False)+json.dumps(b['sections'],ensure_ascii=False)+b['svg']+json.dumps(words,ensure_ascii=False)+'曲谱同步SYMPHONYVII'
fonts=visual.font_css(corpus)
for tag,w,h in [('16x9',3840,2160),('4x3',2880,2160)]:
 last=76 if tag=='16x9' else 74
 phrase=[m for m in b['geometry']['measures'] if 67<=m['source_index']<=last and m['occurrence']==1]
 assert len(phrase)==last-66
 spec={k:v for k,v in b.items() if k not in ('curve','time_at','score','alignment','audio','notes')}
 spec.update(fonts=fonts,frames=[state],width=w,height=h,number='VII',cover_layout='mahler9',cover_words=words,cover_selection={'measures':[m['svg_id'] for m in phrase],'staves':['P1:1','P4:1','P11:1']},font_audit_output=str(ROOT/f'output/cover-font-audit-{tag}.json'),font_audit_selector='body>svg>text')
 visual.run_browser(spec,ROOT/f'output/visual-revision-04/covers/封面-{tag}.svg','cover')
 print(tag,flush=True)
