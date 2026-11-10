"""82-second evidence film: all robot frames replay measured qpos, never physics."""
import os
for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[key]='1'
os.environ.setdefault('MUJOCO_GL','egl')
import argparse
import hashlib
import json
from pathlib import Path
import sys
import numpy as np
import mujoco
from PIL import Image,ImageDraw,ImageOps
import imageio_ffmpeg

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from harness.kit import Plant
from harness.scenes import write_scene
from policy.kinematics import ArmModel
from tools.render import label,GREEN,BLUE,WHITE,MUTED

BG=(9,16,24)
PANEL=(17,29,40)


class Replay:
    def __init__(self,path):
        self.path=path
        self.report=json.loads((path/'report.json').read_text())
        self.trace=path/'trace.npz'
        if not self.trace.exists():
            self.trace=path/'replay.npz'
        with np.load(self.trace,allow_pickle=False) as z:
            self.data={k:z[k].copy() for k in ('time','qpos','q','state','true_force','estimated_force','true_force_filtered') if k in z}
        spec=self.report['scene_specification']
        scene=write_scene('replay-'+hashlib.sha256(json.dumps(spec,sort_keys=True).encode()).hexdigest()[:16],spec['walls'],spec['exit'])
        self.plant=Plant(scene=scene)
        self.renderer=mujoco.Renderer(self.plant.model,width=960,height=540)
        for g in range(self.plant.model.ngeom):
            if (self.plant.model.geom(g).name or '').startswith('wall_'):
                self.plant.model.geom_rgba[g,3]=.42
        walls=np.asarray(self.report['scene_specification']['walls'])
        points=walls.reshape(-1,2)
        self.center=(points.max(axis=0)+points.min(axis=0))/2
        self.extent=float(np.ptp(points,axis=0).max())
        self.camera=mujoco.MjvCamera()
        self.camera.azimuth=-65
        self.camera.elevation=-62
        self.end=float(self.data['time'][-1])

    def index(self,t):
        return int(np.argmin(abs(self.data['time']-t)))

    def frame(self,t,size=(916,516),close=False):
        i=self.index(t)
        self.plant.data.qpos[:]=self.data['qpos'][i]
        mujoco.mj_forward(self.plant.model,self.plant.data)
        self.camera.lookat[:]=[*self.data['qpos'][i,:2],.65] if close else [*self.center,.3]
        self.camera.distance=2.7 if close else self.extent*1.70
        self.camera.elevation=-35 if close else -62
        self.renderer.update_scene(self.plant.data,camera=self.camera)
        image=ImageOps.contain(Image.fromarray(self.renderer.render()),size,Image.Resampling.LANCZOS)
        canvas=Image.new('RGB',size,BG)
        canvas.paste(image,((size[0]-image.width)//2,(size[1]-image.height)//2))
        return canvas

    def event_time(self,state):
        return next((e['time']+self.report['policy_handoff_at_secs'] for e in self.report['controller_events']
                     if e['target']==state and e.get('distance',0)>1.),20.)


def panel(draw,replay,t,title):
    i=replay.index(t)
    draw.rounded_rectangle((960,104,1256,620),radius=12,fill=PANEL)
    label(draw,(980,126),title,18,GREEN,True)
    label(draw,(980,166),str(replay.data['state'][i]).replace('_',' '),22,WHITE,True)
    label(draw,(980,202),f'{t:05.1f} simulated seconds',15,MUTED)
    label(draw,(980,247),'RIGHT HAND FORCE / N',15,WHITE,True)
    label(draw,(980,274),'Estimate',13,GREEN)
    label(draw,(1093,274),'Contact (filtered)',12,BLUE)
    start=max(0,i-300)
    values=[replay.data['estimated_force'][start:i+1,1,1],replay.data['true_force_filtered'][start:i+1,1,1]]
    ymax=max(20.,np.ceil(max(float(v.max()) for v in values)/10)*10)
    for value in (0,ymax/2,ymax):
        y=438-value/ymax*125
        draw.line((1005,y,1236,y),fill=(42,59,72))
        label(draw,(977,y-6),f'{value:g}',11,MUTED)
    for v,color in zip(values,(GREEN,BLUE)):
        if len(v)>1:
            points=[(1005+j*230/(len(v)-1),438-np.clip(x,0,ymax)/ymax*125) for j,x in enumerate(v)]
            draw.line(points,fill=color,width=2)
    label(draw,(1005,451),'Last 6 simulated seconds',12,MUTED)
    label(draw,(980,507),'Right arm: wall feeler',16,WHITE)
    label(draw,(980,540),'Left arm: forward probe',16,WHITE)
    label(draw,(980,582),'Joints + pelvis IMU only',15,GREEN,True)


def build(cohort,comparisons,native,output,frames_only=False):
    summary=json.loads((cohort/'summary.json').read_text())
    # Reproducible demonstration selection, not part of the aggregate score.
    successful=sorted((r for r in summary['rows'] if r['exited']),key=lambda r:r['seed'])
    hero=Replay(ROOT/next(r['report_path'] for r in successful if r['seed']==26111500).rsplit('/',1)[0])
    unique=[]
    for row in successful:
        if row['topology_sha256'] not in {r['topology_sha256'] for r in unique}:
            unique.append(row)
        if len(unique)==4:
            break
    grids=[hero if r['seed']==hero.report['seed'] else Replay((ROOT/r['report_path']).parent) for r in unique]
    controls=[Replay(ROOT/f'evidence/cohorts/final-control-{mode}/{mode}-26111500') for mode in ('neutral','touch_off')]
    control_summaries={mode:json.loads((comparisons/mode/'summary.json').read_text()) for mode in ('neutral','touch_off','touch_shuffled','map_only')}
    native_summary=json.loads(native.read_text())
    kin=ArmModel()
    contacts=[]
    for i in range(0,len(hero.data['time']),4):
        if np.linalg.norm(hero.data['true_force'][i,1])>3:
            hand=kin.evaluate(hero.data['q'][i],hero.data['qpos'][i,3:7])['right']['position']
            contacts.append((hero.data['time'][i],hero.data['qpos'][i,:2]+hand[:2]))
    output.parent.mkdir(parents=True,exist_ok=True)
    sample_times=[0,12,28,38,46,55,63,70,78]
    sample_dir=output.parent/(output.stem+'-frames')
    sample_dir.mkdir(exist_ok=True)
    fps=24
    writer=None
    if not frames_only:
        writer=imageio_ffmpeg.write_frames(str(output),(1280,720),fps=fps,codec='libx264',quality=7,
                macro_block_size=1,output_params=['-movflags','+faststart','-crf','20'])
        writer.send(None)
    indexes=[int(t*fps) for t in sample_times] if frames_only else range(82*fps)
    for n in indexes:
        t=n/fps
        frame=Image.new('RGB',(1280,720),BG)
        d=ImageDraw.Draw(frame)
        label(d,(24,23),'RIGHT HAND RULE',30,WHITE,True)
        label(d,(1055,33),'SIMULATION',15,GREEN,True)
        if t<5:
            label(d,(45,120),'A ROUTE FOUND BY TOUCH',29,WHITE,True)
            label(d,(45,170),'Physical hand contacts / simulation reference',17,MUTED)
            cutoff=7+(hero.end-7)*t/5
            for stamp,p in contacts:
                if stamp>cutoff:
                    break
                x,y=(p-hero.center)*125+[680,380]
                y=760-y
                d.ellipse((x-2,y-2,x+2,y+2),fill=GREEN)
            label(d,(45,650),'NO CAMERA.  NO LIDAR.  NO SUPPLIED MAP.',25,GREEN,True)
        elif t<9:
            label(d,(45,170),'RIGHT',75,WHITE,True)
            label(d,(45,260),'HAND RULE',75,GREEN,True)
            label(d,(50,390),'A blindfolded G1 follows the wall.',29,WHITE)
            label(d,(50,453),'Scripted touch navigation on NVIDIA GR00T locomotion.',21,MUTED)
            label(d,(50,530),'The base is free. Every contact is simulated physics.',19,MUTED)
        elif t<51:
            if t<35:
                stamp=7+(hero.end-7)*(t-9)/26
                text=f'Complete run / {(hero.end-7)/26:.1f}x speed'
                close=False
                title='THE RIGHT-HAND RULE'
            elif t<43:
                stamp=max(7,hero.event_time('ARC')-1)+(t-35)*1.8
                text='Wall disappears. Seek contact around the right corner. / 1.8x'
                close=True
                title='WALL LOST'
            else:
                stamp=max(7,hero.event_time('BACKOFF')-1)+(t-43)*1.8
                text='Probe meets a wall. Back away, then turn left. / 1.8x'
                close=True
                title='WALL AHEAD'
            frame.paste(hero.frame(stamp,close=close),(24,104))
            d=ImageDraw.Draw(frame)
            panel(d,hero,stamp,title)
            label(d,(24,646),text,19,WHITE,True)
            label(d,(24,681),'Saved simulation states; transparent walls expose the motion.',14,MUTED)
        elif t<59:
            label(d,(24,105),'WHAT CHANGES WHEN TOUCH IS REMOVED?',25,GREEN,True)
            for k,(replay,mode,title) in enumerate(zip(controls,('neutral','touch_off'),('NEUTRAL / STAND','TOUCH OFF'))):
                stamp=7+(min(50,replay.end)-7)*(t-51)/8
                frame.paste(replay.frame(stamp,(600,370),close=True),(24+k*632,180))
                d=ImageDraw.Draw(frame)
                label(d,(36+k*632,145),title,18,WHITE,True)
                s=control_summaries[mode]
                label(d,(36+k*632,575),f'{s["exits"]}/{s["episodes"]} matched-seed exits',23,WHITE,True)
            label(d,(24,650),'Same dynamics and sensors. Touch-off zeros the navigation force signal.',18,MUTED)
            label(d,(24,682),'Controls run for up to 400 simulated seconds; clips show saved states.',14,MUTED)
        elif t<67:
            label(d,(24,91),'DIFFERENT MAZES. THE SAME FROZEN CONTROLLER.',22,GREEN,True)
            for k,replay in enumerate(grids):
                x,y=24+(k%2)*632,132+(k//2)*260
                stamp=7+(replay.end-7)*(t-59)/8
                frame.paste(replay.frame(stamp,(600,225)),(x,y))
                d=ImageDraw.Draw(frame)
                label(d,(x+9,y+8),f'SEED {replay.report["seed"]}',14,WHITE,True)
                label(d,(x+9,y+196),f'EXIT / {replay.end:.1f} s',15,GREEN,True)
            label(d,(24,677),f'{summary["exits"]}/{summary["episodes"]} exits over the entire untouched split; all outcomes in the report.',18,WHITE)
        elif t<74:
            label(d,(45,137),'INSIDE HIM\'S RUNNER',31,GREEN,True)
            label(d,(45,220),native_summary['task_status'],35,WHITE,True)
            label(d,(45,300),f'Native ARM64 / exact published image',24,WHITE)
            label(d,(45,355),f'Standard: {native_summary["standard_passes"]}/{native_summary["repeats"]}  |  Maze: {native_summary["task_passes"]}/{native_summary["repeats"]}',27,WHITE,True)
            label(d,(45,412),f'Designated exit: {native_summary["task_exits"]}/{native_summary["repeats"]} / scored from kit traces',23,WHITE)
            label(d,(45,483),'Original physics, gains, deadlines and safety checks.',21,MUTED)
            label(d,(45,522),'Disclosed post-run report-export timeout fix only.',18,MUTED)
            label(d,(45,604),'Image SHA-256: '+native_summary['image_sha256'][:32]+'...',16,MUTED)
        else:
            label(d,(45,122),'100 UNTOUCHED RANDOMIZED EPISODES',25,GREEN,True)
            label(d,(45,192),f'{summary["exits"]}/100',86,WHITE,True)
            label(d,(50,295),'designated exits / nominal control timing',24,WHITE)
            label(d,(50,355),f'{summary["falls"]} falls  /  {summary["episodes_with_hard_findings"]} episodes with limit findings',24,WHITE)
            label(d,(50,405),f'Median successful run: {summary["median_success_seconds"]:.1f} s',23,WHITE)
            label(d,(50,468),'Joints + IMU. No supplied layout. Real contact physics.',22,GREEN,True)
            label(d,(50,538),'NVIDIA GR00T locomotion / Unitree G1 / HIM builder kit',17,MUTED)
            label(d,(50,577),'Code, exact image, controls, and every result:',17,MUTED)
            label(d,(50,614),'github.com/Marc-Dvci/right-hand-rule-g1',23,WHITE,True)
            label(d,(50,668),'Simulation evidence. Hardware qualification and latency stress are documented.',14,MUTED)
        if n in [int(v*fps) for v in sample_times]:
            frame.save(sample_dir/f'{n:05d}.png')
        if writer:
            writer.send(np.asarray(frame))
        if n%(fps*10)==0:
            print(f'Rendered {t:g}/82 seconds',flush=True)
    if writer:
        writer.close()
    for replay in {id(r):r for r in [hero,*grids,*controls]}.values():
        replay.renderer.close()
    provenance=dict(hero=str(hero.path.relative_to(ROOT)),grid_seeds=[r.report['seed'] for r in grids],
        selection='Hero: final seed 26111500. Grid: first four successes with distinct topologies in seed order.',
        simulation='All robot frames use recorded qpos and mj_forward only; no physics steps. Walls are transparent only for replay.',
        duration_seconds=82,fps=fps,native_summary=str(native),
        source_traces={str(r.path.relative_to(ROOT)):hashlib.sha256(r.trace.read_bytes()).hexdigest()
                       for r in [hero,*grids,*controls]})
    output.with_suffix('.json').write_text(json.dumps(provenance,indent=2)+'\n')
    print('Film output:',output,flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--cohort',type=Path,default=ROOT/'reports/final-nominal')
    p.add_argument('--comparisons',type=Path,default=ROOT/'reports/comparisons')
    p.add_argument('--native',type=Path,default=ROOT/'reports/native-summary.json')
    p.add_argument('--output',type=Path,default=ROOT/'dist/result.mp4')
    p.add_argument('--frames-only',action='store_true')
    a=p.parse_args()
    build(a.cohort,a.comparisons,a.native,a.output,a.frames_only)
