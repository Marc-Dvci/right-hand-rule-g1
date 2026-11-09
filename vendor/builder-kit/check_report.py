"""Reject incomplete controller coverage even if an upstream report says within_limits."""
import argparse
import json
import math
from pathlib import Path


def coverage_problem(report):
    if report.get('status') != 'within_limits':
        return 'Review the recorded violation or runtime error.'
    if report.get('safety_checks') is not True or report.get('control_path') != 'submission':
        return 'This did not test a submitted controller with safety enabled.'
    checks = report.get('checks', {})
    if not all(checks.get(k) is True for k in ('command_limits', 'observation_freshness', 'action_timeout', 'joint_speed', 'base_angular_speed', 'thrash_enforcement')):
        return 'Required safety checks were not all enforced.'
    handoff, seconds = report.get('policy_handoff_at_secs'), report.get('seconds')
    if report.get('control_ready') is not True or type(handoff) not in (int, float) or type(seconds) not in (int, float):
        return 'The submitted policy never took control. Startup-only evidence is incomplete.'
    if not math.isfinite(handoff) or not math.isfinite(seconds) or handoff < 0 or seconds - handoff < 10:
        return 'Fewer than 10 simulated seconds after handoff. Increase --seconds and rerun; do not disable checks.'
    if type(report.get('commands')) is not int or report['commands'] < 1:
        return 'No submitted commands were accepted.'
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('output', type=Path)
    parser.add_argument('--counterfactuals', choices=('0', '1'), default='0')
    args = parser.parse_args()
    paths = ([args.output / 'poses' / p / 'report.json' for p in ('standing', 'seated', 'supine', 'prone', 'left_side', 'right_side')]
             if args.counterfactuals == '1' else [args.output / 'report.json'])
    rows = []
    for path in paths:
        try:
            report = json.loads(path.read_text())
            issue = coverage_problem(report) if isinstance(report, dict) else 'Invalid report.'
        except (ValueError, OSError):
            issue = 'Report missing or unreadable.'
        rows.append({'report': str(path), 'problem': issue})
    result = {'status': 'review_required' if any(x['problem'] for x in rows) else 'simulation_checks_complete',
              'hardware_authorization': False, 'reports': rows}
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / 'builder-check.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
    return 2 if any(x['problem'] for x in rows) else 0


if __name__ == '__main__':
    raise SystemExit(main())
