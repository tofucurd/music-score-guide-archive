"""Original full Walter PCM, sequential without inter-movement frame padding."""
from pathlib import Path
import json, hashlib, subprocess, shutil
from prepare_data import W,R,L,load,dump,ref

def file_hash(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        while b:=f.read(4*1024*1024):h.update(b)
    return h.hexdigest()

def main():
    out=W/'audio';out.mkdir(exist_ok=True)
    sources=load(R/'work/revision-04/source-inventory/recording-native-clocks.json')['records']
    recipe=load(L/'pcm24-numeric-evidence-01/recipe-candidate.json')
    ffmpeg=shutil.which('ffmpeg');timeline=load(W/'timeline.json');results=[]
    for movement in timeline['movements']:
        m=movement['movement'];d=load(W/f'data/M{m}/data.json');source=d['source']
        original=Path(next(x['path'] for x in sources if x['movement']==m))
        assert file_hash(original)==source['hash']
        key=f"walter-M{m}-{source['hash'][:16]}-{recipe['recipe_hash'][:12]}"
        old=R/'work/revision-04/final-render/verified-source-pcm'/key
        if old.with_suffix('.s24').exists() and old.with_suffix('.json').exists():
            p=old.with_suffix('.s24');receipt=load(old.with_suffix('.json'))
            assert p.stat().st_size==movement['count']*6
            assert file_hash(p)==receipt['full_pcm_sha256']
        else:
            p=out/f'M{m}.s24';receipt_path=out/f'M{m}.json'
            if p.exists() and receipt_path.exists():
                receipt=load(receipt_path)
                assert p.stat().st_size==movement['count']*6 and file_hash(p)==receipt['full_pcm_sha256']
            else:
                assert shutil.disk_usage(W).free>25*2**30
                tmp=out/f'M{m}.partial.s24'
                args=recipe['args'][:]
                i=args.index('-af')+1;args[i]+=f",atrim=end_sample={movement['count']}"
                print('decode full source M'+str(m),flush=True)
                with original.open('rb') as src,tmp.open('wb') as dst:
                    subprocess.run([ffmpeg,*args],stdin=src,stdout=dst,check=True)
                assert tmp.stat().st_size==movement['count']*6
                tmp.rename(p)
                receipt=dict(source_hash=source['hash'],recipe_hash=recipe['recipe_hash'],
                    output_sample_count=movement['count'],full_pcm_sha256=file_hash(p),
                    terminal_container_padding_excluded=True)
                dump(receipt_path,receipt)
        results.append(dict(movement=m,path=str(p.relative_to(R)),samples=movement['count'],
                            sha256=receipt['full_pcm_sha256'],source_sha256=source['hash']))
        print('verified M'+str(m),flush=True)
    # One ALAC elementary programme. Packet boundaries do not insert silence.
    output=out/'Walter-full-96k24.m4a'
    if not output.exists():
        cmd=[ffmpeg,'-nostdin','-v','error','-n','-f','s24le','-ar','96000','-ac','2','-i','pipe:0',
             '-c:a','alac','-sample_fmt','s32p','-bits_per_raw_sample','24',str(output)]
        h=hashlib.sha256();proc=subprocess.Popen(cmd,stdin=subprocess.PIPE)
        try:
            for record in results:
                with (R/record['path']).open('rb') as f:
                    while b:=f.read(4*1024*1024):h.update(b);proc.stdin.write(b)
            proc.stdin.close();assert proc.wait()==0
        finally:
            if proc.poll() is None:proc.terminate();proc.wait()
        expected=h.hexdigest()
        decoded=subprocess.Popen([ffmpeg,'-v','error','-xerror','-i',str(output),'-map','0:a','-c:a','pcm_s24le','-f','s24le','pipe:1'],stdout=subprocess.PIPE)
        actual=hashlib.sha256();count=0
        while b:=decoded.stdout.read(4*1024*1024):actual.update(b);count+=len(b)
        assert decoded.wait()==0 and count==timeline['total_samples']*6 and actual.hexdigest()==expected
        dump(out/'manifest.json',dict(sources=results,output=ref(output),samples=timeline['total_samples'],
            decoded_pcm_sha256=expected,decoded_pcm_exact=True,no_added_samples=True,sample_rate=96000,bits=24,channels=2))
    print('complete audio',output,flush=True)

if __name__=='__main__':main()
