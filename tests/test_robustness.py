import numpy as np
from harness.kit import Plant, ROOT
from harness.robustness import configure


def test_damping_uncertainty_changes_real_actuator_bias_without_compounding():
    p=Plant(scene=ROOT/'scene/flat.xml')
    configure(p,{'velocity_damping_scale':.8})
    q,dq=p.q(),np.zeros(29)
    kp,kd=np.full(29,60.),np.full(29,1.5)
    for _ in range(3):
        p._apply_arrays(q,dq,kp,kd,np.zeros(29))
        np.testing.assert_allclose(p.model.actuator_biasprm[p.actuators,2],-1.2)
        np.testing.assert_allclose(p.model.actuator_gainprm[p.actuators,0],60.)


def test_declared_push_reaches_canonical_plant_force_and_clears_after_interval():
    p=Plant(scene=ROOT/'scene/flat.xml')
    push=dict(start=15.,duration=.25,body='pelvis',force=[0.,10.,0.])
    configure(p,{'push':push})
    p.apply_push(p._push,15.1)
    np.testing.assert_array_equal(p.data.xfrc_applied[p.base,:3],[0,10,0])
    p.apply_push(p._push,16.)
    np.testing.assert_array_equal(p.data.xfrc_applied,np.zeros_like(p.data.xfrc_applied))
