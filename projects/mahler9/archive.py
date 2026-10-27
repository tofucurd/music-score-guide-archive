"""Archive entry: restore compressed project text only; never render implicitly."""
from pathlib import Path
import argparse,gzip,json,hashlib
ROOT=Path(__file__).resolve().parent

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['restore','inventory'])
    args=parser.parse_args()
    manifest=json.loads((ROOT/'restore-manifest.json').read_text())
    if args.action=='inventory':
        print('Final renderer: work/score-sync-02/render_full.py')
        print('Archive closure is incomplete. Read README.md and external-inputs.json before rendering.')
        return
    for item in manifest['files']:
        if not item['compressed']:continue
        data=gzip.decompress((ROOT/item['archive_path']).read_bytes())
        if len(data)!=item['bytes'] or hashlib.sha256(data).hexdigest()!=item['sha256']:
            raise SystemExit('Archive payload differs: '+item['path'])
        target=ROOT/item['path']
        if target.exists() and target.read_bytes()!=data:raise SystemExit('Refusing to replace '+item['path'])
        target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
    print('Text payloads restored. No alignment, render, or test was run.')
if __name__=='__main__':main()
