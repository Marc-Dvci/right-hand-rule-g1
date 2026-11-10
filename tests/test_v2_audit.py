"""Synthetic records exercise audit integrity without opening held-out episodes."""
import json
from pathlib import Path
import numpy as np
import pytest
from harness.maze_catalog import wall_segments
from harness.randomization import parameters
from tools.check_native_episode import REQUIRED_CHECKS
import tools.audit_v2 as module


@pytest.fixture
def evidence(tmp_path,monkeypatch):
    root=tmp_path
    for name in ('config','policy/models','evaluation','evidence/test/case'):
        (root/name).mkdir(parents=True,exist_ok=True)
    for name in ('navigation','control','deployment'):
        (root/f'config/{name}.json').write_text('{}')
    (root/'evaluation/frozen-v2.json').write_text('{}')
    protocol=dict(holdout_seeds=[17],holdout_topologies=[0],command_delays_ms=[0],time_limit_seconds=600,
        per_delay_target_exit_rate=.9,controls=dict(modes=[],matched_first_n_seeds=0))
    frozen=dict(protocol=protocol,files={'harness/evaluate.py':'evaluator','review/evaluation_v2_protocol.json':'protocol',
        'harness/catalog_evaluate.py':'generator','harness/maze_catalog.py':'catalog'})
    monkeypatch.setattr(module,'ROOT',root)
    monkeypatch.setattr(module,'check',lambda:frozen)
    random=parameters(17)
    random['command_latency_steps']=0
    width=random['corridor_width']
    exit_spec=dict(axis=0,value=2.5*width+.25,sign=1,min_y=1.5*width,max_y=2.5*width)
    target=root/'evidence/test/case'
    np.savez_compressed(target/'trace.npz',time=[20.,21.],
        qpos=[[exit_spec['value']-.1,2*width,.74],[exit_spec['value']+.1,2*width,.74]],q=np.zeros((2,29)))
    report=dict(seed=17,layout_id=0,mode='navigate',split='geometry_holdout',nominal_command_latency_ms=0,
        controller_sha256=module.source_digest(),freeze_sha256=module.sha256(root/'evaluation/frozen-v2.json'),
        controller_parameters={},control_parameters={},transport_config={},transport_adapter=True,
        evaluation_sha256='evaluator',protocol_sha256='protocol',
        scene_generator_sha256={'harness/catalog_evaluate.py':'generator','harness/maze_catalog.py':'catalog'},
        safety_checks=True,control_path='submission',checks={name:True for name in REQUIRED_CHECKS},
        randomized_parameters=random,robustness_stress=None,mujoco_version='3.3.7',numpy_version='2.5.2',
        corridor_width=width,scene_specification=dict(walls=wall_segments(0,width),exit=exit_spec),
        exited=True,wrong_exit=False,policy_calls=2,seconds=21.,reason=None,warnings={},
        policy_handoff_at_secs=2.,commands=1000,thrash_peak=.3,
        touch_metrics={'peak_500hz_hand_force_n':10.},
        contact_loads={'peak_sum_contact_magnitudes_n':[5.,10.],'peak_nonhand_wall_sum_n':0.})
    path=target/'report.json'
    path.write_text(json.dumps(report))
    return root,path,report


def test_audit_independently_checks_trace_and_requires_complete_inventory(evidence):
    root,path,report=evidence
    result=module.audit([root/'evidence/test'],root/'audit.json',require_controls=False)
    assert result['primary_gate_passed']
    report['exited']=False
    path.write_text(json.dumps(report))
    with pytest.raises(ValueError,match='trajectory score'):
        module.audit([root/'evidence/test'],root/'bad.json',require_controls=False)
    with pytest.raises(ValueError,match='inventory'):
        module.audit([],root/'missing.json',require_controls=False)


def test_audit_rejects_easier_exit_and_disabled_checker(evidence):
    root,path,report=evidence
    report['scene_specification']['exit']['value']-=.1
    path.write_text(json.dumps(report))
    with pytest.raises(ValueError,match='designated exit'):
        module.audit([root/'evidence/test'],root/'bad.json',require_controls=False)
    report['safety_checks']=False
    path.write_text(json.dumps(report))
    with pytest.raises(ValueError,match='checker path'):
        module.audit([root/'evidence/test'],root/'bad.json',require_controls=False)


def test_audit_rejects_missing_generator_provenance_and_duplicate_episode(evidence):
    root,path,report=evidence
    report['scene_generator_sha256']={}
    path.write_text(json.dumps(report))
    with pytest.raises(ValueError,match='generator provenance'):
        module.audit([root/'evidence/test'],root/'bad.json',require_controls=False)
    report['scene_generator_sha256']={'harness/catalog_evaluate.py':'generator','harness/maze_catalog.py':'catalog'}
    path.write_text(json.dumps(report))
    with pytest.raises(ValueError,match='Duplicate'):
        module.audit([root/'evidence/test',root/'evidence/test'],root/'bad.json',require_controls=False)
