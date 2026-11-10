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
    hero=json.loads((ROOT/'reports/v2/hero-metrics.json').read_text())
    primitive_path=ROOT/'reports/v2/primitive-summary.json'
    primitives=json.loads(primitive_path.read_text()) if primitive_path.exists() else None
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
        '| Intervention | 0 ms | 20 ms | 40 ms | Limit findings (0/20/40 ms) |','|---|---:|---:|---:|---:|']
    for mode,title in zip(modes,titles):
        values=[]
        findings=[]
        for delay in (0,20,40):
            rows=[r for r in audit['rows'] if r['mode']==mode and r['delay_ms']==delay and r['seed'] in seeds]
            values.append(f'{sum(r["exited"] for r in rows)}/{len(rows)}')
            findings.append(str(sum(r['hard_findings'] for r in rows)))
        lines.append('| '+title+' | '+' | '.join(values)+' | '+' / '.join(findings)+' |')
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
        f'- Constant command age identified correctly in **{sum(r["calibration"]["selected_frames"]==r["delay_ms"]//20 and not r["calibration"].get("error") for r in audit["rows"] if r["mode"]=="navigate")}/300** held-out primary trials. The controller receives no evaluator delay label; fit confidence remains a relative residual heuristic.',
        f'- Fresh development qualification: {development["episodes"]} episodes across all 92 development layouts and all three delays; see `reports/v2/development-summary.json`.',
        f'- Separate damping/push stresses: {stress["exits"]}/{stress["episodes"]} exits, {stress["checker_stops"]} checker stops and {stress["actual_limit_findings"]} actual limit findings.',
        f'- Sensor-only command proof: **{proof["policy_calls"]:,} calls**, maximum target/feedforward difference **{proof["maximum_absolute_command_difference"]}**, MuJoCo imported: **{proof["simulator_imported"]}**. '
        'The bundle contains only joint/IMU observations, host readiness, sequence IDs and expected outputs compared after inference.',
        '- Original locomotion export parity: 10,000 recorded histories per network, maximum action difference 3.58e-6. This validates the pretrained network export, not hardware transfer.',
        '- Independent final audit checks exact source, config, dependencies, seeds, walls, randomization, active checks and geometric crossing scores. Portable motions can be rescored without a physics engine.','',
        'A neutral-control process failed before model/policy initialization because its generated scene was unavailable on the shared Windows-mounted path. '
        'The original log is retained; only that missing trial was rerun on a byte-identical frozen Linux copy. '
        'The remaining controls used that copy as well. No policy, physics, settings, seed or outcome was changed; '
        'see `review/results/v2-infrastructure-incidents.json`.','',
        '## Force-estimator and odometry audit','',
        f'The disclosed film hero has **{hero["component_rmse_n"]:.3f} N component RMSE** and '
        f'**{hero["mean_hand_vector_rmse_n"]:.3f} N mean-hand vector RMSE**, '
        f'{100*hero["mean_hand_vector_rmse_fraction_of_target"]:.1f}% of the {hero["force_target_n"]:.3f} N target. '
        'These use causally aligned, bandwidth-matched evaluator forces after startup. '
        'Historical fields named `force_vector_rmse_n` average components; the new analysis explicitly distinguishes vector-norm RMSE. '
        'The original 25% force-error goal is not passed under the vector definition.',
        '',f'Its aligned endpoint odometry error is **{hero["endpoint_odometry_error_m"]:.3f} m**. '
        'This is one disclosed demonstration, not a cohort-wide estimator guarantee. '
        'The trajectory/map remains logging-only.',
        '', '![Force and aligned odometry errors](force-and-odometry.svg)','',
        '## Material limits and improvements still needed','',
        f'- Peak final hand load: **{max(s["peak_hand_load_n"] for s in primary):.2f} N**; '
        f'peak nonhand wall load: **{max(s["peak_nonhand_wall_load_n"] for s in primary):.2f} N**. '
        'These are 500 Hz sums of individual contact magnitudes. The original 20 N gate remains unmet; softened arms sometimes transferred load to the body.',
        '- Instrumented compliant-wall qualification and improved collision avoidance/compliance are the highest priorities before hardware. Inferred-force thresholds do not bound transient load.',
        '- Calibration assumes a free-space start and a constant 0/20/40 ms command age. Arbitrary varying delays, hardware actuator filtering and model mismatch remain unqualified.',
        '- Foot odometry drifts. The touch map and wall-heading fit remain logging-only; no memory traversal or guided-hand mode is implemented.',
        ('- The supplemental 50-run wall/inner/outer sets are reported below. The original full low-force goal remains unmet.' if primitives else '- The supplemental 50-run wall/inner/outer sets are still running.')+' Broader geometry and dynamic-obstacle qualification remain unexecuted. This is a 3x3 perfect-maze task.',
        '- Physical G1 results, all-pose recovery and hardware authorization are absent. Simulation reliability does not establish universal superiority over competitors on different tasks.','',
        '## All primary failures','']
    failures=sorted((r for r in audit['rows'] if r['mode']=='navigate' and not r['exited']),key=lambda r:(r['delay_ms'],r['seed']))
    if failures:
        lines+=['| Delay | Seed | Layout | Seconds | Outcome / last state |','|---|---:|---:|---:|---|']
        for r in failures:
            report=json.loads((ROOT/r['report_path']).read_text())
            state=report['controller_events'][-1]['target'] if report['controller_events'] else 'ARMING'
            outcome=r['reason'] or ('wrong entrance' if report['wrong_exit'] else
                ('navigation hold' if state in ('STOP','GUARD') and r['seconds']<599.99 else 'time budget'))
            lines.append(f'| {r["delay_ms"]} ms | {r["seed"]} | {r["layout"]} | {r["seconds"]:.2f} | {outcome} / {state} |')
    else:
        lines.append('No primary navigation failures in this declared cohort.')
    if primitives:
        lines+=['','## Supplemental original-plan primitives','',
            'These 150 nominal-delay trials were declared and executed after the frozen geometry holdout, with the same unchanged controller. '
            'Each primitive uses 50 fresh randomized seeds and a 150-second budget. Corner scores below are geometric exit crossings in the authored L-wall scenes; '
            'they do not establish a physical low-force corner envelope.','',
            '| Primitive | Exits | Checker stops | Limit findings | Peak hand load | Peak body-wall load |',
            '|---|---:|---:|---:|---:|---:|']
        for s in primitives['strata']:
            lines.append(f'| {s["scene"]} | {s["exits"]}/50 | {s["checker_stops"]} | {s["actual_limit_findings"]} | {s["peak_hand_load_n"]:.2f} N | {s["peak_nonhand_wall_load_n"]:.2f} N |')
        lines+=['',f'Straight-wall runs meeting the complete exit/contact-distance/20 N condition: **{primitives["strata"][0]["straight_full_gate_passes"]}/50**. '
            f'Wall contact onsets detected within 200 ms: {100*primitives["wall_detection_fraction_200ms"]:.2f}%; '
            f'false-contact sample fraction: {100*primitives["wall_false_contact_fraction"]:.2f}%; '
            f'wall runs meeting the vector-RMSE goal: {primitives["wall_runs_meeting_vector_error_goal"]}/50. '
            'The instantaneous false-contact comparison includes short gait-contact gaps while the filtered navigation signal remains positive; the declared 1% criterion is unmet. '
            'The exact thresholds, sample definitions and per-run values are in the declared protocol and `reports/v2/primitive-summary.json`. '
            'This supplemental set is not the 100-topology holdout and was not used to retune V2.','']
    lines+=['','Full per-episode reports, hashes, controls and native outcomes are included in the source ZIP and release evidence. '
        'The film uses measured states only; hero/grid selection is the first four successful nominal seeds, disclosed in `dist/result.json`.','']
    (target/'RESULTS.md').write_text('\n'.join(lines))
    (ROOT/'review/V2_RESULTS.md').write_text('\n'.join(lines)
        .replace('(cohort.svg)','(../evaluation/results/v2/cohort.svg)')
        .replace('(force-and-odometry.svg)','(../evaluation/results/v2/force-and-odometry.svg)'))
    print('Wrote audited V2 tables, complete failure list and results figure')


if __name__=='__main__':
    main()
