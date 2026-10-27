"""Resumable 4K HEVC delivery of the exact continuous Walter programme."""
from pathlib import Path
from datetime import datetime,timezone
import subprocess,shutil,hashlib,json,os,signal,time,sys,fcntl
W=Path(__file__).resolve().parent;R=W.parents[1]
from frame_params import Frames as Renderer
from runtime_environment import runtime_environment
from render_finalize import record_intent,finish_verified
load=lambda p:json.loads(Path(p).read_text())
def dump(p,value):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
def ref(p):
    p=Path(p);return dict(path=str(p.relative_to(R)),bytes=p.stat().st_size,sha256=digest(p))

FFMPEG=shutil.which('ffmpeg');FFPROBE=shutil.which('ffprobe')

def digest(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        while b:=f.read(4*1024*1024):h.update(b)
    return h.hexdigest()

def check_space():
    assert shutil.disk_usage(W).free>25*2**30,'25 GiB space reserve reached'

def probe(p):
    return json.loads(subprocess.check_output([FFPROBE,'-v','error','-show_streams','-show_format','-of','json',str(p)]))

def main():
    lock=(W/'render.lock').open('a')
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    inputs=load(W/'render-inputs.json');audit=load(W/'asset-audit.json')
    assert inputs['environment']==runtime_environment(),'Runtime changed: require fresh source/visual QA and new run, never mix chunks'
    assert audit['all_92_sections_present'] and not audit['failures']
    assert (W/'visual-review.json').exists(),'Actual final-format three-person visual review is required'
    review=load(W/'visual-review.json');assert review['render_input_sha256']==digest(W/'render-inputs.json')
    assert review.get('approved') is True and len(set(review.get('reviewers',[])))>=3
    def verify_inputs(include_audio=False):
        for item in inputs['files']:
            if not include_audio and item['path'].endswith('Walter-full-96k24.m4a'):continue
            p=R/item['path'];assert p.stat().st_size==item['bytes'] and digest(p)==item['sha256'],p
    verify_inputs(include_audio=True)
    audio=load(R/'work/score-sync-01/audio/manifest.json');audio_path=R/audio['output']['path']
    assert digest(audio_path)==audio['output']['sha256'] and audio['decoded_pcm_exact']
    run_hash=hashlib.sha256((digest(W/'render-inputs.json')+digest(Path(__file__))).encode()).hexdigest()
    out=W/'final-render'/run_hash[:16];out.mkdir(parents=True,exist_ok=True)
    status_path=W/'render-status.json';journal_path=out/'chunks.json'
    journal=load(journal_path) if journal_path.exists() else dict(run_hash=run_hash,chunks=[])
    assert journal['run_hash']==run_hash
    r=Renderer();total=r.timeline['total_frames'];begun=time.monotonic()
    status=dict(pid=os.getpid(),run_hash=run_hash,run_directory=str(out),total_frames=total,
                started_utc=datetime.now(timezone.utc).isoformat())
    def progress(**updates):
        status.update(updates,updated_utc=datetime.now(timezone.utc).isoformat(),free_bytes=shutil.disk_usage(W).free)
        tmp=status_path.with_suffix('.tmp');dump(tmp,status);tmp.replace(status_path)
    def stop(signum,frame):raise KeyboardInterrupt('User/process stop signal '+str(signum))
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
    caffeinate=subprocess.Popen(['/usr/bin/caffeinate','-i','-w',str(os.getpid())])
    active=None;active_pgid=None
    try:
        recovery=finish_verified(out/'finalization-intent.json',run_hash,[out/'result.json',W/'delivery.json'],cleanup_paths=[out/c['file'] for c in journal['chunks']])
        if recovery:
            dump(out/'cleaned-generated-chunks.json',dict(files=[c['file'] for c in journal['chunks']],after_verified_output=recovery['sha256'],recovered=True))
            progress(stage='complete',output=recovery['output'],completed_frames=total,encoder_pid=None)
            return
        completed=0
        for ch in journal['chunks']:
            assert ch['start']==completed and digest(out/ch['file'])==ch['sha256']
            completed=ch['end']
        progress(stage='rendering',completed_frames=completed)
        for start in range(completed,total,1800):
            check_space();verify_inputs();assert inputs['environment']==runtime_environment(),'Runtime changed during render';end=min(start+1800,total);name=f'video-{start:08d}.mov';target=out/name;tmp=out/f'video-{start:08d}.partial.mov'
            if tmp.exists():tmp.unlink()
            if target.exists():target.unlink() # Unjournaled product of an interrupted chunk only.
            # Rebuild only this chunk's deterministic source-time scene commands.
            config=out/f'frames-{start:08d}.json'
            dump(config,dict(frames=[r.frame(f) for f in range(start,end)]))
            args=['node',str(W/'run_scene.mjs'),'--config',str(config),'--video',str(tmp),'--height','2160','--silent','--scene',inputs['scene_module'],'--progress',str(out/'chunk-progress.json')]
            active=subprocess.Popen(args,cwd=R,start_new_session=True);active_pgid=active.pid
            progress(stage='rendering',chunk_start=start,chunk_end=end,encoder_pid=active.pid)
            while active.poll() is None:
                check_space();time.sleep(2)
                cp=out/'chunk-progress.json'
                if cp.exists():
                    ps=load(cp)
                    if start<=ps.get('frame',-1)<end:progress(current_frame=ps['frame'],chunk_frames=ps['frames'],chunk_average_fps=ps['average_fps'])
            assert active.wait()==0;active=None;active_pgid=None
            verify_inputs()
            assert inputs['environment']==runtime_environment(),'Runtime changed during chunk'
            config.unlink()
            meta=probe(tmp);v,=meta['streams']
            assert v['codec_name']=='hevc' and v['width']==3840 and v['height']==2160
            assert v['pix_fmt']==inputs['video']['pixel_format'] and v['avg_frame_rate']=='60/1' and int(v['nb_frames'])==end-start
            tmp.rename(target);journal['chunks'].append(dict(start=start,end=end,file=name,sha256=digest(target)))
            journal_tmp=journal_path.with_suffix('.tmp');dump(journal_tmp,journal);journal_tmp.replace(journal_path)
            progress(stage='chunk_verified',completed_frames=end,current_frame=end)
        check_space();progress(stage='assembling',completed_frames=total,encoder_pid=None)
        listing=out/'concat.txt';listing.write_text(''.join('file '+ch['file']+'\n' for ch in journal['chunks']))
        partial=out/'continuous.partial.mov'
        if partial.exists():partial.unlink()
        active=subprocess.Popen([FFMPEG,'-nostdin','-v','error','-xerror','-n','-f','concat','-safe','1','-i',str(listing),
            '-i',str(audio_path),'-map','0:v:0','-map','1:a:0','-c','copy','-tag:v','hvc1','-video_track_timescale','60000',
            '-map_metadata','-1','-map_chapters','-1','-movflags','+faststart',str(partial)])
        assert active.wait()==0;active=None
        meta=probe(partial);assert len(meta['streams'])==2
        v=next(s for s in meta['streams'] if s['codec_type']=='video');a=next(s for s in meta['streams'] if s['codec_type']=='audio')
        assert int(v['nb_frames'])==total and v['avg_frame_rate']=='60/1'
        assert v['codec_name']=='hevc' and v['profile']=='Rext' and v['pix_fmt']==inputs['video']['pixel_format']
        assert v['width']==inputs['video']['width'] and v['height']==inputs['video']['height']
        assert a['codec_name']=='alac' and int(a['sample_rate'])==96000 and int(a['bits_per_raw_sample'])==24
        assert int(a['duration_ts'])==r.timeline['total_samples'] and a['time_base']=='1/96000'
        progress(stage='verifying_full_audio')
        active=subprocess.Popen([FFMPEG,'-v','error','-xerror','-i',str(partial),'-map','0:a:0','-c:a','pcm_s24le','-f','s24le','pipe:1'],stdout=subprocess.PIPE)
        pcm_hash=hashlib.sha256();count=0
        while b:=active.stdout.read(4*1024*1024):pcm_hash.update(b);count+=len(b)
        assert active.wait()==0;active=None
        assert count==r.timeline['total_samples']*6 and pcm_hash.hexdigest()==audio['decoded_pcm_sha256']
        progress(stage='decoding_and_checking_all_video_timestamps')
        active=subprocess.Popen([FFPROBE,'-v','error','-select_streams','v:0','-show_entries','frame=best_effort_timestamp',
                                 '-of','csv=p=0',str(partial)],stdout=subprocess.PIPE,text=True)
        frames=0
        for line in active.stdout:
            token=line.strip().split(',')[0]
            if not token:continue
            assert token.isdigit(),line
            assert int(token)==frames*1000,(frames,token)
            frames+=1
            if frames%6000==0:progress(qc_decoded_frames=frames)
        assert active.wait()==0 and frames==total;active=None
        delivery=R/'output/score-sync-02/马勒第九交响曲-Walter-连续曲谱同步-2160p.mov'
        delivery.parent.mkdir(parents=True,exist_ok=True)
        result=dict(output=str(delivery),sha256=digest(partial),bytes=partial.stat().st_size,
            frames=total,samples=r.timeline['total_samples'],seconds=r.timeline['total_samples']/96000,
            video=inputs['video'],audio=dict(codec='alac',rate=96000,bits=24,channels=2),
            decoded_pcm_sha256=pcm_hash.hexdigest(),all_frame_timestamps_verified=True,
            visual_review=ref(W/'visual-review.json'),all_voices_audit=ref(W/'asset-audit.json'),
            actual_full_audition=False,original_recording_unedited=True,run_hash=run_hash)
        record_intent(out/'finalization-intent.json',run_hash,partial,result)
        finish_verified(out/'finalization-intent.json',run_hash,[out/'result.json',W/'delivery.json'],cleanup_paths=[out/c['file'] for c in journal['chunks']])
        dump(out/'cleaned-generated-chunks.json',dict(files=[c['file'] for c in journal['chunks']],after_verified_output=result['sha256']))
        progress(stage='complete',output=str(delivery),completed_frames=total,encoder_pid=None)
    except BaseException as error:
        # The session leader can already have failed while owned children survive.
        if active_pgid is not None:
            try:os.killpg(active_pgid,signal.SIGTERM)
            except ProcessLookupError:pass
            deadline=time.monotonic()+15
            while time.monotonic()<deadline:
                try:os.killpg(active_pgid,0)
                except ProcessLookupError:break
                time.sleep(.1)
            else:
                try:os.killpg(active_pgid,signal.SIGKILL)
                except ProcessLookupError:pass
            if active:active.wait()
        elif active and active.poll() is None:
            active.terminate()
            try:active.wait(timeout=15)
            except subprocess.TimeoutExpired:active.kill();active.wait()
        progress(stage='stopped',error=str(error),encoder_pid=None)
        raise
    finally:
        if caffeinate.poll() is None:caffeinate.terminate();caffeinate.wait()

if __name__=='__main__':main()
