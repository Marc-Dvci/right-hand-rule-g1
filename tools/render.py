"""Render a measured episode. Never step physics or alter the saved trajectory."""
import os
for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[key] = '1'
os.environ.setdefault('MUJOCO_GL','egl')
import argparse
import json
from pathlib import Path
import sys
import numpy as np
import mujoco
from PIL import Image, ImageDraw, ImageFont
import imageio_ffmpeg

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from harness.kit import Plant
from policy.kinematics import ArmModel

GREEN = (61,224,174)
BLUE = (100,174,255)
WHITE = (239,244,248)
MUTED = (166,182,196)
FONT_ROOT = Path('/usr/share/fonts/truetype/dejavu')


def font(size, bold=False):
    name = 'DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf'
    return ImageFont.truetype(str(FONT_ROOT/name),size)


def label(draw, xy, text, size=22, fill=WHITE, bold=False):
    draw.text(xy,text,font=font(size,bold),fill=fill)


def render(episode, output, duration=75, fps=24):
    report = json.loads((episode/'report.json').read_text())
    scene = Path(report['scene'])
    if not scene.exists():
        scene = ROOT/'scene'/scene.name
    plant = Plant(scene=scene)
    with np.load(episode/'trace.npz') as z:
        data = {k:z[k].copy() for k in z.files}
    if not report['exited']:
        raise ValueError('Choose a successfully evaluated episode for this demonstration')
    model, mjdata = plant.model, plant.data
    renderer = mujoco.Renderer(model,height=720,width=1280)
    # Rendering transparency only; it does not change the saved physics.
    for g in range(model.ngeom):
        name = model.geom(g).name or ''
        if name.startswith('wall_'):
            model.geom_rgba[g,3] = .40
    camera = mujoco.MjvCamera()
    camera.azimuth = -65
    camera.elevation = -65
    walls = json.loads(scene.with_suffix('.json').read_text())['walls']
    all_points = np.asarray(walls).reshape(-1,2)
    center = (all_points.max(axis=0)+all_points.min(axis=0))/2
    extent = max(np.ptp(all_points,axis=0))
    camera.lookat[:] = [*center,.25]
    camera.distance = extent*1.65
    times = data['time']
    start_time, end_time = 7., float(times[-1])
    end_position = data['qpos'][-1,:2]
    kin = ArmModel()
    contact_points = []
    for j in range(0,len(times),5):
        if np.linalg.norm(data['true_force'][j,1]) > 3:
            hand = kin.evaluate(data['q'][j],data['qpos'][j,3:7])['right']['position']
            contact_points.append((j,data['qpos'][j,:2]+hand[:2]))
    output.parent.mkdir(parents=True,exist_ok=True)
    writer = imageio_ffmpeg.write_frames(str(output),(1280,720),fps=fps,codec='libx264',
        quality=7,macro_block_size=1,output_params=['-movflags','+faststart','-crf','21'])
    writer.send(None)
    sample_frames = {0, int(12*fps),int(35*fps),int(55*fps),int(70*fps)}
    samples = output.parent/(output.stem+'-frames')
    samples.mkdir(parents=True,exist_ok=True)
    for n in range(int(duration*fps)):
        film_time = n/fps
        if film_time < 6:
            simulated_time = start_time+(end_time-start_time)*film_time/6
        elif film_time < 10:
            simulated_time = start_time+5
        elif film_time < 49:
            simulated_time = start_time+(end_time-start_time)*(film_time-10)/39
        elif film_time < 64:
            arc_indices = np.flatnonzero(data['state']=='ARC')
            a = times[arc_indices[0]] if len(arc_indices) else start_time+15
            simulated_time = min(end_time,a+(film_time-49)*1.8)
        else:
            simulated_time = end_time
        i = int(np.argmin(abs(times-simulated_time)))
        mjdata.qpos[:] = data['qpos'][i]
        mujoco.mj_forward(model,mjdata)
        if 49 <= film_time < 64:
            camera.lookat[:] = [*data['qpos'][i,:2],.65]
            camera.distance = 3.2
            camera.elevation = -50
        else:
            camera.lookat[:] = [*center,.25]
            camera.distance = extent*1.65
            camera.elevation = -65
        renderer.update_scene(mjdata,camera=camera)
        frame = Image.fromarray(renderer.render()).convert('RGBA')
        overlay = Image.new('RGBA',frame.size)
        d = ImageDraw.Draw(overlay)
        d.rectangle((0,0,1280,95),fill=(10,17,25,235))
        d.rectangle((0,632,1280,720),fill=(10,17,25,235))
        label(d,(38,23),'RIGHT HAND RULE',32,bold=True)
        label(d,(1020,30),'SIMULATION',17,GREEN,bold=True)
        if film_time < 6:
            overlay = Image.new('RGBA',frame.size,(7,13,20,255))
            d = ImageDraw.Draw(overlay)
            label(d,(55,50),'A ROUTE FOUND BY TOUCH',32,bold=True)
            label(d,(55,98),'Physical hand contacts  /  simulation reference',21,MUTED)
            p = np.array([point for j,point in contact_points if j<=i])
            scale = 480/max(extent,1)
            for k, point in enumerate(p):
                x,y = (point-center)*scale+[640,370]
                d.ellipse((x-2,720-y-2,x+2,720-y+2),fill=(*GREEN,90))
            label(d,(55,650),'NO CAMERA  /  NO LIDAR  /  NO SUPPLIED LAYOUT',24,GREEN,bold=True)
        elif film_time < 10:
            d.rectangle((0,95,1280,632),fill=(7,13,20,215))
            label(d,(55,175),'RIGHT',75,bold=True)
            label(d,(55,260),'HAND RULE',75,GREEN,bold=True)
            label(d,(60,385),'A blindfolded G1 follows walls through its arm joints.',27)
            label(d,(60,440),'Scripted touch navigation on NVIDIA GR00T locomotion.',21,MUTED)
        elif film_time < 64:
            label(d,(38,650),f'{simulated_time:6.1f} s  |  {str(data["state"][i]).replace("_"," ")}',24,GREEN,bold=True)
            label(d,(680,654),'Transparent walls reveal the saved motion',18,MUTED)
            if film_time < 49:
                label(d,(38,112),f'Continuous replay  /  {(end_time-start_time)/39:.1f}x speed',18,WHITE)
            else:
                label(d,(38,112),'The arm yields. The robot turns toward contact.',21,WHITE,bold=True)
            panel = (910,155,1245,440)
            d.rounded_rectangle(panel,radius=12,fill=(7,13,20,225))
            label(d,(930,176),'RIGHT HAND FORCE',18,bold=True)
            label(d,(930,211),'Estimated',16,GREEN)
            label(d,(1080,211),'Contact truth',16,BLUE)
            left = max(0,i-300)
            for values,color in ((data['estimated_force'][left:i+1,1,1],GREEN),(data['true_force'][left:i+1,1,1],BLUE)):
                if len(values)>1:
                    xy=[(932+j*286/max(len(values)-1,1),400-np.clip(v,0,35)*4.1) for j,v in enumerate(values)]
                    d.line(xy,fill=color,width=2)
            label(d,(932,407),'Last 6 simulated seconds',14,MUTED)
        else:
            d.rectangle((0,95,1280,632),fill=(7,13,20,225))
            label(d,(55,145),'A MEASURED DEVELOPMENT RUN',28,GREEN,bold=True)
            label(d,(55,225),f'{end_time:.1f} s',70,bold=True)
            label(d,(55,315),'Designated exit crossed',27)
            label(d,(55,380),f'Thrash peak: {report["thrash_peak"]:.3f} / 1.500',24)
            label(d,(55,426),f'Kit warnings: {len(report["warnings"])}  |  Policy calls: {report["policy_calls"]:,}',23)
            label(d,(55,498),'Joints + IMU only. Free base. Physical contact.',25,GREEN,bold=True)
            label(d,(55,552),'Local simulation evidence; no hardware performance is claimed.',18,MUTED)
            label(d,(38,654),'RIGHT HAND RULE  /  REPRODUCIBLE ROBOTICS',22,bold=True)
        frame = Image.alpha_composite(frame,overlay).convert('RGB')
        if n in sample_frames:
            frame.save(samples/f'{n:05d}.png')
        writer.send(np.asarray(frame))
        if n%(fps*10)==0:
            print('Rendered',round(film_time,1),'of',duration,'seconds',flush=True)
    writer.close()
    renderer.close()
    metadata = dict(source_episode=str(episode.relative_to(ROOT)),report=report,
                    duration_seconds=duration,fps=fps,width=1280,height=720,size_bytes=output.stat().st_size,
                    rendering='Saved qpos only; no simulation steps; wall transparency is rendering-only')
    output.with_suffix('.json').write_text(json.dumps(metadata,indent=2)+'\n')
    print('Video',output,output.stat().st_size,'bytes',flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--episode',type=Path,required=True)
    p.add_argument('--output',type=Path,default=ROOT/'dist/preview-development.mp4')
    p.add_argument('--seconds',type=int,default=75)
    p.add_argument('--fps',type=int,default=24)
    args = p.parse_args()
    render(args.episode if args.episode.is_absolute() else ROOT/args.episode,args.output,args.seconds,args.fps)
