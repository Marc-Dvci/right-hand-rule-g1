"""Generate judge-facing V2 tables and a figure exclusively from audited results."""
import json
from pathlib import Path
import sys
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.freeze_v2 import check


def main():
    check()
    audit=json.loads((ROOT/'reports/v2/final-audit.json').read_text())
    native=json.loads((ROOT/'reports/v2/native-summary.json').read_text())
    proof=json.loads((ROOT/'review/results/sensor-replay-v2-selected.json').read_text())
    development=json.loads((ROOT/'reports/v2/development-summary.json').read_text())
    stress=json.loads((ROOT/'reports/v2/stress-summary.json').read_text())
    primary=sorted((s for s in audit['strata'] if s['mode']=='navigate'),key=lambda s:s['delay_ms'])
    target=ROOT/'evaluation/results/v2'
    target.mkdir(parents=True,exist_ok=True)
    labels=['0 ms','20 ms','40 ms']
    fig,axes=plt.subplots(1,2,figsize=(11,4.2),layout='constrained')
    fig.set_facecolor('#f5f8fa')
    for ax in axes:
        ax.spines[['top','right']].set_visible(False)
        ax.set_ylim(0,112)
        ax.set_ylabel('Designated exits (%)')
    axes[0].bar(labels,[100*s['exits']/s['episodes'] for s in primary],color='#159b78',width=.6)
    for i,s in enumerate(primary):
        axes[0].text(i,100*s['exits']/s['episodes']+2,f'{s["exits"]}/{s["episodes"]}',ha='center')
    axes[0].axhline(90,linestyle='--',color='#667788',linewidth=1,label='Declared 90% target')
    axes[0].set_title('100 distinct held-out topologies per delay')
    axes[0].legend(loc='lower left',frameon=False)
    modes=['navigate','neutral','touch_off','touch_shuffled']
    titles=['Complete','Neutral','Touch off','Touch delayed 3.4 s']
    colors=['#159b78','#738496','#dc8e3c','#b3618f']
    seeds=set(check()['protocol']['holdout_seeds'][:20])
    for k,(mode,title,color) in enumerate(zip(modes,titles,colors)):
        for i,delay in enumerate((0,20,40)):
            rows=[r for r in audit['rows'] if r['mode']==mode and r['delay_ms']==delay and r['seed'] in seeds]
            count=sum(r['exited'] for r in rows)
            x=i+(k-1.5)*.19
            axes[1].bar(x,100*count/len(rows),width=.18,color=color,label=title if i==0 else None)
            axes[1].text(x,100*count/len(rows)+2,str(count),ha='center',fontsize=8)
    axes[1].set_xticks(range(3),labels)
    axes[1].set_title('Matched first 20 seeds (labels = exit counts)')
    axes[1].legend(loc='lower left',frameon=False,fontsize=8)
    fig.suptitle('RIGHT HAND RULE V2 / 600-second limit / all failures retained',fontsize=13)
    fig.savefig(target/'cohort.svg')
    fig.savefig(target/'cohort.png',dpi=160)
    plt.close(fig)
    lines=['# RIGHT HAND RULE V2: measured results','',
        'A whole contact-navigation controller on joint state and pelvis IMU only. '
        'Navigation is scripted; locomotion uses attributed pretrained NVIDIA GR00T networks. '
        'No camera, supplied layout, simulator position or contact labels enter the deployed controller.','',
        '## Frozen geometry holdout','',
        'The 100 distinct 3x3 spanning-tree topologies exclude all 92 development topologies '
        'and every retired V1 layout. Source/settings were frozen before opening these episodes. '
        'Each trial allows 600 simulated seconds; all failures remain in the denominator.','',
        '| Command delay | Exits | Checker stops | Actual limit findings | Median success | Peak thrash |',
        '|---|---:|---:|---:|---:|---:|']
    for s in primary:
        lines.append(f'| {s["delay_ms"]} ms | {s["exits"]}/{s["episodes"]} | {s["checker_stops"]} | {s["actual_limit_findings"]} | {s["median_success_seconds"]:.2f} s | {s["peak_thrash"]:.3f} |')
    lines+=['','Declared primary gate: **'+('passed' if audit['primary_gate_passed'] else 'not passed')+'**. '
        'This is a simulation qualification for the declared distribution, not a common benchmark against other Arena tasks.','',
        '![V2 exits and matched causal controls](cohort.svg)','',
        '## Matched controls','',
        'First 20 seeds, identical geometry/settings/randomization at each delay. '
        '`touch_shuffled` is the historical name for a fixed 3.4-second delay, not random shuffling.','',
        '| Intervention | 0 ms | 20 ms | 40 ms |','|---|---:|---:|---:|']
    for mode,title in zip(modes,titles):
        values=[]
        for delay in (0,20,40):
            rows=[r for r in audit['rows'] if r['mode']==mode and r['delay_ms']==delay and r['seed'] in seeds]
            values.append(f'{sum(r["exited"] for r in rows)}/{len(rows)}')
        lines.append('| '+title+' | '+' | '.join(values)+' |')
    lines+=['','## Exact-image native ARM64 evidence','',
        f'Standard: **{native["standard_passes"]}/{native["repeats"]}** clean; '
        f'actual maze: **{native["task_passes"]}/{native["repeats"]}** clean, '
        f'**{native["task_exits"]}/{native["repeats"]}** designated exits. '
        f'Peak native thrash: {native["native_peak_thrash"]:.3f}.',
        '',f'Archive SHA-256: `{native["image_sha256"]}`.',
        '',f'[Native workflow]({native["rows"][0]["github_run"]}). '
        'Standard runs use the canonical kit. Task runs disclose a report-export-only '
        'RPC extension from 10 to 60 seconds. Plant, active deadlines and checks are unchanged. '
        'All six starts were attempted on both scenes; startup failures and invalid '
        'penetrations remain recorded. Both suites require review; this is not an all-pose pass.','',
        '## Version-matched supporting evidence','',
        f'- Fresh development qualification: {development["episodes"]} episodes across all 92 development layouts and all three delays; see `reports/v2/development-summary.json`.',
        f'- Separate damping/push stresses: {stress["exits"]}/{stress["episodes"]} exits, {stress["checker_stops"]} checker stops and {stress["actual_limit_findings"]} actual limit findings.',
        f'- Sensor-only command proof: **{proof["policy_calls"]:,} calls**, maximum target/feedforward difference **{proof["maximum_absolute_command_difference"]}**, MuJoCo imported: **{proof["simulator_imported"]}**. '
        'The bundle contains only joint/IMU observations, host readiness, sequence IDs and expected outputs compared after inference.',
        '- Original locomotion export parity: 10,000 recorded histories per network, maximum action difference 3.58e-6. This validates the pretrained network export, not hardware transfer.',
        '- Independent final audit checks exact source, config, dependencies, seeds, walls, randomization, active checks and geometric crossing scores. Portable motions can be rescored without a physics engine.','',
        '## Material limits and improvements still needed','',
        f'- Peak final hand load: **{max(s["peak_hand_load_n"] for s in primary):.2f} N**; '
        f'peak nonhand wall load: **{max(s["peak_nonhand_wall_load_n"] for s in primary):.2f} N**. '
        'These are 500 Hz sums of individual contact magnitudes. The original 20 N gate remains unmet; softened arms sometimes transferred load to the body.',
        '- Instrumented compliant-wall qualification and improved collision avoidance/compliance are the highest priorities before hardware. Inferred-force thresholds do not bound transient load.',
        '- Calibration assumes a free-space start and a constant 0/20/40 ms command age. Arbitrary varying delays, hardware actuator filtering and model mismatch remain unqualified.',
        '- Foot odometry drifts. The touch map and wall-heading fit remain logging-only; no memory traversal or guided-hand mode is implemented.',
        '- The full planned 50-run straight/inner/outer corner gates and broader geometry/dynamic-obstacle qualification remain unexecuted. This is a 3x3 perfect-maze task.',
        '- Physical G1 results, all-pose recovery and hardware authorization are absent. Simulation reliability does not establish universal superiority over competitors on different tasks.','',
        '## All primary failures','']
    failures=sorted((r for r in audit['rows'] if r['mode']=='navigate' and not r['exited']),key=lambda r:(r['delay_ms'],r['seed']))
    if failures:
        lines+=['| Delay | Seed | Layout | Seconds | Checker reason |','|---|---:|---:|---:|---|']
        lines += [f'| {r["delay_ms"]} ms | {r["seed"]} | {r["layout"]} | {r["seconds"]:.2f} | {r["reason"] or "navigation failure / see report"} |' for r in failures]
    else:
        lines.append('No primary navigation failures in this declared cohort.')
    lines+=['','Full per-episode reports, hashes, controls and native outcomes are included in the source ZIP and release evidence. '
        'The film uses measured states only; hero/grid selection is the first four successful nominal seeds, disclosed in `dist/result.json`.','']
    (target/'RESULTS.md').write_text('\n'.join(lines))
    (ROOT/'review/V2_RESULTS.md').write_text('\n'.join(lines).replace('(cohort.svg)','(../evaluation/results/v2/cohort.svg)'))
    print('Wrote audited V2 tables, complete failure list and results figure')


if __name__=='__main__':
    main()
