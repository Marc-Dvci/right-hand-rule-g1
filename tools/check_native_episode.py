"""Require complete submitted control and zero actual findings in a kit episode."""
import argparse
import json
from pathlib import Path

REQUIRED_CHECKS = ('command_protocol', 'command_limits', 'profile_gains',
    'observation_freshness', 'action_timeout', 'robot_state_timeout', 'loop_timeout',
    'joint_speed', 'base_angular_speed', 'fall', 'finite_simulation', 'thrash_enforcement')


def validate(report, builder):
    problems = []
    if builder.get('status') != 'simulation_checks_complete':
        problems.append('Builder qualification did not complete')
    if report.get('status') != 'within_limits' or report.get('reason'):
        problems.append('Kit episode did not finish within limits')
    if report.get('safety_checks') is not True or report.get('control_path') != 'submission':
        problems.append('Submitted image/checking path was not active')
    if report.get('control_ready') is not True or not report.get('commands', 0):
        problems.append('No accepted submitted control')
    handoff = report.get('policy_handoff_at_secs')
    if handoff is None or report.get('seconds', 0)-handoff < 10:
        problems.append('Insufficient post-handoff coverage')
    for name in REQUIRED_CHECKS:
        if report.get('checks', {}).get(name) is not True:
            problems.append('Required check missing: '+name)
    if any(w.get('limits') for w in report.get('warnings', {}).values()):
        problems.append('Actual joint limit findings recorded')
    if problems:
        raise ValueError('; '.join(problems))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('directory', type=Path)
    args = parser.parse_args()
    validate(json.loads((args.directory/'report.json').read_text()),
             json.loads((args.directory/'builder-check.json').read_text()))
    print('Complete submitted-control episode, required checks active, zero limit findings')
