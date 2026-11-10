"""Evaluator-only contact loads. No contact truth crosses the policy boundary."""
from collections import deque
import numpy as np
import mujoco


class LoadMetrics:
    """Sum contact magnitudes before averaging, so opposing loads cannot cancel."""
    def __init__(self, dt):
        self.dt = dt
        self.samples = 0
        self.peak = np.zeros(2)
        self.impulse = np.zeros(2)
        self.above = {threshold: np.zeros(2) for threshold in (20, 40)}
        self.windows = {duration: deque() for duration in (.1, .25)}
        self.totals = {duration: np.zeros(2) for duration in self.windows}
        self.sustained = {duration: np.zeros(2) for duration in self.windows}

    def observe(self, loads):
        loads = np.asarray(loads, dtype=float)
        if loads.shape != (2,) or not np.isfinite(loads).all() or (loads < 0).any():
            raise ValueError('Contact loads must be two finite nonnegative magnitudes')
        self.samples += 1
        self.peak = np.maximum(self.peak, loads)
        self.impulse += loads * self.dt
        for threshold, times in self.above.items():
            times += (loads > threshold) * self.dt
        for duration, window in self.windows.items():
            window.append(loads.copy())
            self.totals[duration] += loads
            if len(window) > round(duration/self.dt):
                self.totals[duration] -= window.popleft()
            self.sustained[duration] = np.maximum(self.sustained[duration], self.totals[duration]/len(window))

    def report(self):
        return dict(sample_rate_hz=1/self.dt, samples=self.samples,
            side_order=['left', 'right'], peak_sum_contact_magnitudes_n=self.peak.tolist(),
            accumulated_load_impulse_ns=self.impulse.tolist(),
            time_above_n_seconds={str(k): v.tolist() for k, v in self.above.items()},
            peak_window_mean_n={str(k): v.tolist() for k, v in self.sustained.items()})


class ContactAudit:
    def __init__(self, plant):
        self.plant = plant
        m = plant.model
        self.hand_geoms = {m.geom(name).id: n for n, side in enumerate(('left', 'right'))
            for name in [f'{side}_touch_hand', *[f'{side}_palm{i}' for i in (1, 2, 3)]]}
        self.walls = {g for g in range(m.ngeom) if (m.geom(g).name or '').startswith('wall_')}
        self.loads = LoadMetrics(float(m.opt.timestep))
        self.nonhand_loads=LoadMetrics(float(m.opt.timestep))
        self.nonhand_wall_peak = 0.
        self.nonhand_wall_seconds = 0.
        self.peak_single_hand_contact = 0.
        self.nonhand_wall_peak_contacts=[]
        self.nonhand_wall_peak_time=None

    def sample(self):
        p = self.plant
        force = np.zeros((2, 3))
        loads = np.zeros(2)
        nonhand_wall_load = 0.
        nonhand_contacts=[]
        for i, contact in enumerate(p.data.contact):
            a, b = (int(g) for g in contact.geom)
            hand = a in self.hand_geoms or b in self.hand_geoms
            wall_robot = (a in self.walls and b in p.robot_geoms) or (b in self.walls and a in p.robot_geoms)
            if not (hand or wall_robot):
                continue
            wrench = np.zeros(6)
            mujoco.mj_contactForce(p.model, p.data, i, wrench)
            magnitude = float(np.linalg.norm(wrench[:3]))
            if hand:
                self.peak_single_hand_contact = max(self.peak_single_hand_contact, magnitude)
                world = contact.frame.reshape(3, 3).T @ wrench[:3]
                if a in self.hand_geoms:
                    force[self.hand_geoms[a]] -= world
                    loads[self.hand_geoms[a]] += magnitude
                if b in self.hand_geoms:
                    force[self.hand_geoms[b]] += world
                    loads[self.hand_geoms[b]] += magnitude
            elif wall_robot:
                nonhand_wall_load += magnitude
                nonhand_contacts.append(dict(geoms=[p.model.geom(a).name,p.model.geom(b).name],
                    geom_ids=[a,b],bodies=[p.model.body(int(p.model.geom_bodyid[g])).name for g in (a,b)],force_n=magnitude))
        self.loads.observe(loads)
        self.nonhand_loads.observe([nonhand_wall_load,0.])
        if nonhand_wall_load>self.nonhand_wall_peak:
            self.nonhand_wall_peak=nonhand_wall_load
            self.nonhand_wall_peak_contacts=nonhand_contacts
            self.nonhand_wall_peak_time=float(p.data.time)
        self.nonhand_wall_seconds += (nonhand_wall_load > .1) * self.loads.dt
        return force

    def report(self):
        return dict(**self.loads.report(), peak_single_hand_contact_n=self.peak_single_hand_contact,
            peak_nonhand_wall_sum_n=self.nonhand_wall_peak,
            nonhand_wall_contact_seconds=self.nonhand_wall_seconds,
            peak_nonhand_wall_contacts=self.nonhand_wall_peak_contacts,
            peak_nonhand_wall_time=self.nonhand_wall_peak_time,
            nonhand_wall_load_metrics={**self.nonhand_loads.report(),'side_order':['nonhand_total','unused']},
            definition='500 Hz; sums of individual contact force magnitudes per hand, including tangential loads. '
                       'These cannot cancel like a resultant. Impulse is accumulated load over the entire episode; '
                       'window means use trailing 100/250 ms (available samples during startup). '
                       'Nonhand wall load excludes hand contacts and floor support. Evaluator truth only.')
