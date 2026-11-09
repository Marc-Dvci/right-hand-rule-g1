"""Produce measured summaries and publication-quality figures, never estimates of missing runs."""
import os
os.environ['MPLBACKEND'] = 'Agg'
os.environ['OPENBLAS_NUM_THREADS'] = '1'
from pathlib import Path
import argparse
import hashlib
import html
import json
import math
import sys
import numpy as np
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]


def hard_findings(report):
    return [dict(joint=joint,**finding) for joint,w in report.get('warnings',{}).items() for finding in w.get('limits',[])]


def summarize(directory,output):
    directory=directory.resolve()
    paths = sorted(directory.rglob('report.json'))
    rows = []
    for path in paths:
        r = json.loads(path.read_text())
        if 'exited' not in r:
            continue
        rows.append(dict(seed=r['seed'],mode=r['mode'],exited=r['exited'],wrong_exit=r['wrong_exit'],
                         seconds=r['seconds'],status=r['status'],reason=r['reason'],hard_findings=hard_findings(r),
                         diagnostic_warnings=len(r['warnings']),thrash_peak=r['thrash_peak'],
                         peak_hand_force_n=r.get('touch_metrics',{}).get('peak_hand_force_n'),
                         controller_sha256=r.get('controller_sha256'),parameters=r.get('controller_parameters'),
                         randomization=r.get('randomized_parameters'),
                         topology_sha256=r.get('topology_sha256'),
                         baseline=r.get('baseline'),
                         peak_500hz_hand_force_n=r.get('touch_metrics',{}).get('peak_500hz_hand_force_n'),
                         peak_applied_torque_fraction=r.get('peak_applied_torque_fraction'),
                         latency_ms=r.get('nominal_command_latency_ms'),
                         report_path=str(path.relative_to(ROOT)),report_sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    n = len(rows)
    if not n:
        raise ValueError('No episode reports found')
    successes = sum(r['exited'] for r in rows)
    p = successes/n
    z = 1.96
    center = (p+z*z/(2*n))/(1+z*z/n)
    half = z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/(1+z*z/n)
    summary = dict(episodes=n,exits=successes,exit_rate=p,wilson_95_interval=[max(0.,center-half),min(1.,center+half)],
        zero_hard_findings_exits=sum(r['exited'] and not r['hard_findings'] and not r['reason'] for r in rows),
        falls=sum(r['reason']=='fall' for r in rows),episodes_with_hard_findings=sum(bool(r['hard_findings']) for r in rows),
        wrong_exits=sum(r['wrong_exit'] for r in rows),peak_thrash=max(r['thrash_peak'] for r in rows),
        checker_stops=sum(bool(r['reason']) for r in rows),
        unique_topologies=len({r['topology_sha256'] for r in rows if r['topology_sha256']}),
        peak_500hz_hand_force_n=max((r['peak_500hz_hand_force_n'] or 0) for r in rows),
        median_success_seconds=float(np.median([r['seconds'] for r in rows if r['exited']])) if successes else None,
        controller_hashes=sorted({r['controller_sha256'] or 'unrecorded' for r in rows}),
        baseline_hashes=sorted({r['baseline']['source_sha256'] for r in rows if r['baseline']}),
        evidence_kind='in-process kit harness; no native container or hardware claim',rows=rows)
    output.mkdir(parents=True,exist_ok=True)
    (output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    with (output/'episodes.jsonl').open('w') as f:
        for row in rows:
            f.write(json.dumps(row)+'\n')
    fig,axes = plt.subplots(1,2,figsize=(10,4),layout='constrained')
    axes[0].bar(['Exited','Other'],[successes,n-successes],color=['#22b98c','#738395'])
    axes[0].set(ylabel='Episodes',title=f'{successes}/{n} measured exits')
    axes[1].scatter([r['seconds'] for r in rows],[r['thrash_peak'] for r in rows],
                    c=['#22b98c' if r['exited'] else '#738395' for r in rows],s=22)
    axes[1].axhline(1.5,color='#c44a48',ls='--',label='Kit thrash threshold')
    axes[1].set(xlabel='Simulated seconds',ylabel='Peak weighted RMS',title='Task outcome and motion')
    axes[1].legend()
    fig.savefig(output/'cohort.svg')
    fig.savefig(output/'cohort.png',dpi=180)
    fig.savefig(output/'cohort.pdf')
    plt.close(fig)
    table = ''.join(f'<tr><td>{r["seed"]}</td><td>{html.escape(r["mode"])}</td><td>{"EXIT" if r["exited"] else "FAIL"}</td><td>{r["seconds"]:.1f}</td><td>{r["thrash_peak"]:.3f}</td><td>{len(r["hard_findings"])}</td></tr>' for r in rows)
    page = f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>RIGHT HAND RULE — evidence</title>
<style>body{{margin:0;background:#0c141d;color:#ecf2f6;font:16px system-ui}}main{{max-width:1050px;margin:auto;padding:48px 24px}}h1{{font-size:44px;letter-spacing:-2px}}.accent{{color:#3de0ae}}.cards{{display:flex;gap:18px;flex-wrap:wrap}}.card{{padding:24px;background:#152331;border-radius:12px;min-width:180px}}strong{{display:block;font-size:36px}}p{{color:#b3c2d0;line-height:1.6}}img{{width:100%;background:white;border-radius:12px;margin:30px 0}}table{{width:100%;border-collapse:collapse}}td,th{{padding:12px;text-align:left;border-bottom:1px solid #283949}}th{{cursor:pointer;color:#3de0ae}}input{{background:#152331;color:white;padding:12px;border:1px solid #365163;border-radius:6px}}code{{overflow-wrap:anywhere}}</style>
<main><span class="accent">MEASURED ROBOTICS</span><h1>RIGHT HAND RULE</h1><p>Joint state + IMU. Scripted touch navigation on NVIDIA pretrained locomotion. These are local harness measurements; native container and hardware qualification are separate.</p>
<div class="cards"><div class="card"><strong class="accent">{successes}/{n}</strong>exits</div><div class="card"><strong>{summary["falls"]}</strong>falls</div><div class="card"><strong>{summary["peak_thrash"]:.3f}</strong>peak thrash / 1.500</div></div>
<img src="cohort.svg" alt="Measured exit counts and thrash by episode duration"><p>95% Wilson interval for exit rate: {100*(center-half):.1f}–{100*(center+half):.1f}%. {summary["episodes_with_hard_findings"]} episodes recorded actual limit findings. Diagnostic target clipping is retained separately in the JSON.</p>
<input id="filter" placeholder="Filter seed or outcome" aria-label="Filter episodes"><table><thead><tr><th>Seed</th><th>Control</th><th>Outcome</th><th>Seconds</th><th>Thrash</th><th>Limit findings</th></tr></thead><tbody>{table}</tbody></table>
<p>Download <a href="summary.json">summary.json</a> and <a href="episodes.jsonl">episodes.jsonl</a> for parameters, source digests and references to every raw report.</p></main>
<script>const rows=[...document.querySelectorAll('tbody tr')];document.querySelector('#filter').oninput=e=>rows.forEach(r=>r.hidden=!r.textContent.toLowerCase().includes(e.target.value.toLowerCase()));document.querySelectorAll('th').forEach((h,i)=>h.onclick=()=>{{const b=document.querySelector('tbody');[...b.rows].sort((a,c)=>a.cells[i].textContent.localeCompare(c.cells[i].textContent,undefined,{{numeric:true}})).forEach(r=>b.append(r));}});</script></html>'''
    (output/'index.html').write_text(page)
    print(json.dumps({k:v for k,v in summary.items() if k!='rows'},indent=2))


def episode_figures(episode,output):
    output.mkdir(parents=True,exist_ok=True)
    with np.load(episode/'trace.npz') as z:
        t = z['time']
        fig,axes = plt.subplots(3,1,figsize=(10,8),sharex=True,layout='constrained')
        for side,n in (('Left probe',0),('Right feeler',1)):
            axis = axes[n]
            component,sign = (0,-1) if n==0 else (1,1)
            axis.plot(t,sign*z['true_force'][:,n,component],label='Simulated contact force',lw=.8,color='#528cdd')
            observation_time = z['observation_time'] if 'observation_time' in z else t
            axis.plot(observation_time,sign*z['estimated_force'][:,n,component],label='Joint-based estimate',lw=.8,color='#159d76')
            axis.set(ylabel='Force (N)',title=side)
            axis.legend(loc='upper right')
        axes[2].plot(t,z['thrash'],color='#159d76',lw=1)
        axes[2].axhline(1.5,color='#c44a48',ls='--',label='Kit threshold')
        axes[2].set(xlabel='Simulated time (s)',ylabel='Weighted RMS',title='Thrash monitor')
        axes[2].legend()
        for ext in ('svg','pdf','png'):
            fig.savefig(output/f'force-and-safety.{ext}',dpi=180)
        plt.close(fig)


if __name__=='__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--cohort',type=Path)
    p.add_argument('--episode',type=Path)
    p.add_argument('--output',type=Path,default=ROOT/'reports/development')
    a = p.parse_args()
    if a.cohort:
        summarize(a.cohort,a.output)
    if a.episode:
        episode_figures(a.episode,a.output)
