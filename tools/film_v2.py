"""82-second V2 film, using recorded states and audited version-matched results."""
import os
os.environ.setdefault('MUJOCO_GL','egl')
os.environ['OPENBLAS_NUM_THREADS']='1'
import argparse
import hashlib
import json
from pathlib import Path
import sys
import numpy as np
from PIL import Image,ImageDraw
import imageio_ffmpeg
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.film import Replay,panel,BG
from tools.render import label,GREEN,WHITE,MUTED


def build(audit_path,native_path,output,frames_only=False):
    audit=json.loads(audit_path.read_text())
    native=json.loads(native_path.read_text())
    rows=sorted((r for r in audit['rows'] if r['mode']=='navigate' and r['delay_ms']==0 and r['exited']),key=lambda r:r['seed'])
    if len(rows)<4:
        raise ValueError('Four nominal successful traces are needed for the disclosed demonstration selection')
    grids=[Replay((ROOT/r['report_path']).parent) for r in rows[:4]]
    hero=grids[0]
    contact=np.flatnonzero(np.linalg.norm(hero.data['true_force_filtered'][:,1],axis=1)>3.)
    if not len(contact):
        raise ValueError('No measured right-hand contact for the opening clip')
    intro_start=max(7.,float(hero.data['time'][contact[0]])-1.)
    corner_times={}
    for state in ('ARC','BACKOFF'):
        events=[e for e in hero.report['controller_events'] if e['target']==state]
        if not events:
            raise ValueError('Selected hero has no actual '+state+' event; do not label an unrelated clip')
        corner_times[state]=events[0]['time']+hero.report['policy_handoff_at_secs']
    primary=sorted((s for s in audit['strata'] if s['mode']=='navigate'),key=lambda s:s['delay_ms'])
    matched_seeds=set(sorted({r['seed'] for r in audit['rows'] if r['mode']=='navigate'})[:20])
    fps=24
    samples=[0,12,32,44,56,65,73,79]
    sample_dir=output.parent/(output.stem+'-frames')
    sample_dir.mkdir(parents=True,exist_ok=True)
    writer=None
    if not frames_only:
        writer=imageio_ffmpeg.write_frames(str(output),(1280,720),fps=fps,codec='libx264',
            macro_block_size=1,output_params=['-movflags','+faststart','-crf','20'])
        writer.send(None)
    for n in ([int(t*fps) for t in samples] if frames_only else range(82*fps)):
        t=n/fps
        frame=Image.new('RGB',(1280,720),BG)
        d=ImageDraw.Draw(frame)
        label(d,(24,24),'RIGHT HAND RULE / V2',30,WHITE,True)
        label(d,(1050,35),'SIMULATION',15,GREEN,True)
        if t<8:
            frame.paste(hero.frame(min(hero.end,intro_start+t),(670,510),close=True),(586,108))
            d=ImageDraw.Draw(frame)
            label(d,(45,160),'A MAZE',46,GREEN,True)
            label(d,(45,225),'FOUND BY TOUCH',42,GREEN,True)
            label(d,(45,325),'NO CAMERA. NO SUPPLIED MAP.',23,WHITE,True)
            label(d,(45,380),'Joint state + pelvis IMU only.',23,WHITE)
            label(d,(45,448),'Right arm: wall feeler',21,MUTED)
            label(d,(45,486),'Left arm: forward probe',21,MUTED)
            label(d,(45,562),'Scripted navigation',19,WHITE)
            label(d,(45,596),'Pretrained NVIDIA GR00T locomotion',17,MUTED)
            label(d,(45,674),'Recorded contact response / 1x speed / transparent walls for replay',17,MUTED)
        elif t<52:
            if t<40:
                stamp=7+(hero.end-7)*(t-8)/32
                caption=f'Complete navigation / {(hero.end-7)/32:.1f}x speed / seed {hero.report["seed"]}'
                close=False
                title='FOLLOW THE WALL'
            else:
                state='ARC' if t<46 else 'BACKOFF'
                stamp=min(hero.end,max(7,corner_times[state]-1)+(t-(40 if t<46 else 46))*1.5)
                caption='Corner response / 1.5x speed / saved simulation states'
                close=True
                title='WALL LOST' if t<46 else 'WALL AHEAD'
            frame.paste(hero.frame(stamp,close=close),(24,104))
            d=ImageDraw.Draw(frame)
            panel(d,hero,stamp,title)
            label(d,(24,648),caption,19,WHITE,True)
            label(d,(24,684),'Walls are transparent for replay. Every robot frame comes from measured qpos.',14,MUTED)
        elif t<62:
            label(d,(24,91),'DIFFERENT GEOMETRY. THE SAME FROZEN CONTROLLER.',22,GREEN,True)
            for k,replay in enumerate(grids):
                x,y=24+(k%2)*632,132+(k//2)*260
                stamp=7+(replay.end-7)*(t-52)/10
                frame.paste(replay.frame(stamp,(600,225)),(x,y))
                d=ImageDraw.Draw(frame)
                label(d,(x+8,y+8),f'LAYOUT {replay.report["layout_id"]} / SEED {replay.report["seed"]}',14,WHITE,True)
                label(d,(x+8,y+196),f'EXIT / {replay.end:.1f} s',15,GREEN,True)
            label(d,(24,678),'First four successful nominal seeds; aggregate results include every failure.',17,MUTED)
        elif t<70:
            label(d,(45,130),'DOES TOUCH CAUSE THE RESULT?',30,GREEN,True)
            label(d,(45,195),'Matched first 20 seeds / each command-delay stratum',22,MUTED)
            for i,mode in enumerate(('navigate','neutral','touch_off','touch_shuffled')):
                title={'navigate':'Complete controller','neutral':'Neutral / stand','touch_off':'Touch removed','touch_shuffled':'Touch delayed by 3.4 seconds'}[mode]
                values=[]
                for delay in (0,20,40):
                    subset=[r for r in audit['rows'] if r['mode']==mode and r['delay_ms']==delay and r['seed'] in matched_seeds]
                    values.append(f'{delay} ms: {sum(r["exited"] for r in subset)}/{len(subset)}')
                values='    '.join(values)
                label(d,(45,275+i*80),title,20,WHITE,True)
                label(d,(45,306+i*80),values,20,MUTED)
            label(d,(45,658),'Other than the stated intervention, settings and randomization remain matched.',16,MUTED)
        elif t<76:
            label(d,(45,135),'THE COMPLETE IMAGE ON NATIVE ARM64',28,GREEN,True)
            label(d,(45,230),f'Standard: {native["standard_passes"]}/{native["repeats"]}  /  Maze: {native["task_passes"]}/{native["repeats"]}',32,WHITE,True)
            label(d,(45,300),f'Designated maze exits: {native["task_exits"]}/{native["repeats"]}',27,WHITE)
            label(d,(45,390),'Original physics, active checks, gains and control deadlines.',21,MUTED)
            label(d,(45,435),'Disclosed post-run report-export timeout extension only.',20,MUTED)
            label(d,(45,505),'All floor-start outcomes retained; both suites require review.',20,WHITE)
            label(d,(45,575),'Image SHA-256: '+native['image_sha256'][:40]+'...',15,MUTED)
        else:
            label(d,(45,120),'100 DISTINCT UNSEEN TOPOLOGIES',30,GREEN,True)
            for i,s in enumerate(primary):
                label(d,(45,205+i*72),f'{s["delay_ms"]:2d} ms command delay:  {s["exits"]}/{s["episodes"]} exits',32,WHITE,True)
            label(d,(45,445),'600-second limit per trial. Every failure retained.',21,MUTED)
            label(d,(45,493),'Excessive contact impulses remain a limit before hardware.',20,WHITE)
            label(d,(45,535),'Simulation evidence. Hardware qualification is still required.',19,MUTED)
            label(d,(45,605),'github.com/Marc-Dvci/right-hand-rule-g1',24,GREEN,True)
        if n in {int(s*fps) for s in samples}:
            frame.save(sample_dir/f'{n:05d}.png')
        if writer:
            writer.send(np.asarray(frame))
        if n%(10*fps)==0:
            print(f'Rendered {t:g}/82 seconds',flush=True)
    if writer:
        writer.close()
    for replay in grids:
        replay.renderer.close()
    provenance=dict(duration_seconds=82,fps=fps,hero=str(hero.path.relative_to(ROOT)),
        grid=[str(r.path.relative_to(ROOT)) for r in grids],
        selection='First four successful nominal held-out episodes in seed order. Opening: first filtered right-hand contact above 3 N. Corners: first recorded ARC/BACKOFF events. Failures remain in all aggregate denominators.',
        rendering='Recorded qpos, mj_forward only, no physics stepping. Wall transparency is rendering only. The complete navigation clip starts at 7 s, after startup/calibration.',
        source_traces={str(r.path.relative_to(ROOT)):hashlib.sha256(r.trace.read_bytes()).hexdigest() for r in grids},
        audit_sha256=hashlib.sha256(audit_path.read_bytes()).hexdigest(),
        native_summary_sha256=hashlib.sha256(native_path.read_bytes()).hexdigest())
    output.with_suffix('.json').write_text(json.dumps(provenance,indent=2)+'\n')


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--audit',type=Path,default=ROOT/'reports/v2/final-audit.json')
    p.add_argument('--native',type=Path,default=ROOT/'reports/v2/native-summary.json')
    p.add_argument('--output',type=Path,default=ROOT/'dist/result.mp4')
    p.add_argument('--frames-only',action='store_true')
    a=p.parse_args()
    build(a.audit,a.native,a.output,a.frames_only)
