import numpy as np
from harness.kit import Plant, ROOT
from harness.randomization import parameters, apply, SensorNoise


def test_randomization_is_seeded_and_changes_effective_contact_friction():
    params = parameters(17)
    assert params == parameters(17)
    assert params != parameters(18)
    p = Plant(scene=ROOT/'scene/flat.xml')
    before_mass = p.model.body_mass.copy()
    before_strength = p.model.jnt_actfrcrange[p.joints].copy()
    apply(p,params)
    assert not np.array_equal(before_mass,p.model.body_mass)
    np.testing.assert_allclose(p.model.jnt_actfrcrange[p.joints],before_strength*params['motor_strength'])
    floor = p.model.geom('safety_floor').id
    assert p.model.geom_friction[floor,0] == params['floor_friction']
    for g in np.flatnonzero(p.model.geom_priority==1):
        assert p.model.geom_friction[g,0] == params['floor_friction']


def test_sensor_noise_stays_inside_allowed_fields_and_preserves_unit_quaternion():
    a,b = SensorNoise(11,parameters(11)),SensorNoise(11,parameters(11))
    obs = dict(q=np.zeros(29),dq=np.zeros(29),quat=[1,0,0,0],gyro=[0,0,0])
    for t in (0.,1.,200.):
        x,y = a.observe(obs,t),b.observe(obs,t)
        assert set(x) == {'q','dq','quat','gyro'}
        for key in x:
            np.testing.assert_array_equal(x[key],y[key])
            assert np.isfinite(x[key]).all()
        np.testing.assert_allclose(np.linalg.norm(x['quat']),1.,atol=1e-12)
