"""Apply a composed original-to-target clock to a complete donor in one stereo R3 run."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

import numpy as np
import soundfile as sf


def sha(path):
    with path.open('rb') as handle:
        return hashlib.file_digest(handle,'sha256').hexdigest()


def keyframes(source, target, sr):
    """Simplify on target-time error, bounded at every supplied knot."""
    keep = {0,len(source)-1}
    pending = [(0,len(source)-1)]
    while pending:
        lo,hi = pending.pop()
        if hi<=lo+1:
            continue
        x = source[lo+1:hi]
        estimate = target[lo] + (x-source[lo]) * ((target[hi]-target[lo])/(source[hi]-source[lo]))
        error = abs(estimate-target[lo+1:hi])
        idx = int(np.argmax(error))
        if error[idx] > .0008*sr:
            mid = lo+1+idx
        elif source[hi]-source[lo] > sr:
            mid = (hi+lo)//2
        else:
            continue
        keep.add(mid)
        pending.extend(((lo,mid),(mid,hi)))
    i = sorted(keep)
    return np.column_stack((source[i],target[i]))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('source','reference','clock','out'):
        p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--source-sha256',required=True,help='Digest of the original donor recording')
    args = p.parse_args()
    if sha(args.source)!=args.source_sha256:
        raise ValueError('The recording does not match the original-donor receipt')
    donor, ref = sf.info(args.source), sf.info(args.reference)
    sr = donor.samplerate
    if ref.samplerate!=sr or donor.channels!=2:
        raise ValueError('Requires native stereo donor and matching reference rate')
    table = np.atleast_1d(np.genfromtxt(args.clock,names=True,delimiter=','))
    values = np.column_stack((table['source_s'],table['target_s']))
    if not np.isfinite(values).all():
        raise ValueError('Invalid clock')
    src,target = np.rint(values.T*sr).astype('int64')
    if (len(src)<2 or np.any(np.diff(src)<=0) or np.any(np.diff(target)<=0)
            or src[0]<0 or src[-1]>donor.frames or target[0]!=0 or target[-1]!=ref.frames):
        raise ValueError('Supply a strictly increasing full-target clock inside the original audio')
    begin,end = int(src[0]),int(src[-1])
    keys = keyframes(src-begin,target,sr)
    err = float(np.max(abs(np.interp(src-begin,keys[:,0],keys[:,1])-target))/sr)
    if err>.0008:
        raise ValueError('Time-map export lost detail')
    args.out.mkdir(parents=True,exist_ok=True)
    dest = args.out/'transplant.flac'
    if dest.exists():
        raise FileExistsError(dest)
    with tempfile.TemporaryDirectory(prefix='original-one-shot-') as tmp:
        scratch = Path(tmp)
        infile,outfile = scratch/'original.wav',scratch/'stretched.wav'
        time_map = args.out/'engine-keyframes.txt'
        np.savetxt(time_map,keys[1:-1],fmt='%d')
        # Binary-power headroom is exactly representable for the decoded 16/24-bit PCM.
        with sf.SoundFile(args.source) as original, sf.SoundFile(infile,'w',sr,donor.channels,subtype='FLOAT') as stage:
            original.seek(begin)
            for data in original.blocks(blocksize=131072,frames=end-begin,dtype='float32',always_2d=True):
                stage.write(data*.5)
        engine = ['rubberband','-q','-3','--centre-focus','--ignore-clipping',
                  '-t',str(ref.frames/(end-begin)),'-M',str(time_map),str(infile),str(outfile)]
        version = subprocess.check_output(['rubberband','--version'],text=True,stderr=subprocess.STDOUT).strip()
        subprocess.run(engine,check=True)
        output = sf.info(outfile)
        if (output.frames!=ref.frames or output.samplerate!=sr or output.channels!=donor.channels
                or output.subtype!='FLOAT'):
            raise ValueError(f'Engine output mismatch: {output}')
        peak = max(float(np.max(abs(block))) for block in sf.blocks(outfile,blocksize=131072,dtype='float32'))
        if peak>=.99999:
            raise ValueError('Insufficient working headroom')
        gain = min(2.,.999/peak) if peak else 2.
        with tempfile.TemporaryDirectory(dir=args.out) as publishing:
            final = Path(publishing)/'transplant.flac'
            with sf.SoundFile(final,'w',sr,donor.channels,subtype='PCM_24',format='FLAC') as stream:
                for data in sf.blocks(outfile,blocksize=131072,dtype='float32'):
                    stream.write(data*gain)
            record = dict(source_sha256=args.source_sha256,reference_sha256=sha(args.reference),
                          clock_sha256=sha(args.clock),engine_map_sha256=sha(time_map),
                          original_sample_range=[begin,end],engine_keys_including_endpoints=len(keys),
                          max_map_export_error_ms=1000*err,engine='Rubber Band R3 '+version,
                          engine_options=engine[1:7],target_to_donor_duration_ratio=ref.frames/(end-begin),
                          generations_of_time_stretch=1,continuous_stereo_passes=1,joins=0,
                          prior_render_inputs=[],source_headroom=.5,final_net_gain=.5*gain,
                          peak_at_half_amplitude=peak,frames=ref.frames,samplerate=sr,
                          channels=donor.channels,output_subtype='PCM_24',sha256=sha(final))
            (args.out/'receipt.json').write_text(json.dumps(record,indent=2)+'\n')
            os.replace(final,dest)
        print(json.dumps(record),flush=True)


if __name__=='__main__':
    main()
