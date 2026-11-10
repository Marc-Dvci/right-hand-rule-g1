"""Validate evaluation boundaries before any simulator or held-out scene opens."""
from pathlib import Path


def validate_episode(protocol, *, layout, seed, seconds, mode, delay,
                     final=False, root=None, parameters=None, control=None):
    if delay not in (0, 1, 2):
        raise ValueError('Unsupported command delay')
    modes = ['navigate', *protocol['controls']['modes']]
    if mode not in modes:
        raise ValueError('Mode is outside the declared evaluation protocol')
    if not final:
        if layout not in protocol['development_topologies']:
            raise ValueError('Refusing to open a held-out geometry during development')
        return
    if seconds != protocol['time_limit_seconds']:
        raise ValueError('Final episode must use the declared time limit')
    seeds = protocol['holdout_seeds']
    if seed not in seeds or protocol['holdout_topologies'][seeds.index(seed)] != layout:
        raise ValueError('Final seed/topology pair does not match the declared split')
    if mode != 'navigate' and seeds.index(seed) >= protocol['controls']['matched_first_n_seeds']:
        raise ValueError('Control episode is outside the declared matched subset')
    root = Path(root).resolve()
    for value, name in ((parameters, 'navigation'), (control, 'control')):
        if value is None or Path(value).resolve() != root / f'config/{name}.json':
            raise ValueError('Final episode must use the selected frozen configuration')


def validate_cohort(protocol, *, layouts, delays, mode, final=False):
    if not layouts or len(set(layouts)) != len(layouts):
        raise ValueError('Cohort needs distinct nonempty topology IDs')
    if not delays or len(set(delays)) != len(delays) or any(d not in (0, 1, 2) for d in delays):
        raise ValueError('Cohort needs distinct supported delay strata')
    if mode not in ['navigate', *protocol['controls']['modes']]:
        raise ValueError('Unknown evaluation mode')
    if final:
        expected = protocol['holdout_topologies']
        if mode != 'navigate':
            expected = expected[:protocol['controls']['matched_first_n_seeds']]
        if list(layouts) != expected:
            raise ValueError('Final cohort must include the entire declared topology subset')
    elif any(index not in protocol['development_topologies'] for index in layouts):
        raise ValueError('Development cannot open held-out geometries')
