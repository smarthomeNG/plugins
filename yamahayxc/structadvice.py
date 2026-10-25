"""Recommend yamahayxc item structs for a device from its getFeatures response."""

from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class StructAdvice:
    """item structs fitting a device, and the matching feature keys for the smartVISU widget catalog"""

    structs: tuple[str, ...]
    widget_features: tuple[str, ...]


@dataclass(frozen=True)
class _Block:
    """a struct building block: the struct name, the widget feature key it enables (if any) and when a device has it"""

    struct: str
    widget: str | None
    present: Callable[[dict, set[str]], bool]


def _zone_ids(features: dict) -> set[str]:
    return {zone.get('id') for zone in features.get('zone', [])}


def _main_funcs(features: dict) -> set[str]:
    for zone in features.get('zone', []):
        if zone.get('id') == 'main':
            return set(zone.get('func_list', []))
    return set()


def _has_zone(zone_id: str) -> Callable[[dict, set[str]], bool]:
    return lambda features, main: zone_id in _zone_ids(features)


# struct order is the order they are listed in a device struct, widget order the catalog's
_BLOCKS = (
    _Block('amp', None, lambda features, main: True),
    _Block('link', 'link', lambda features, main: 'link_control' in main),
    _Block('netusb', 'netusb', lambda features, main: 'netusb' in features),
    _Block('tuner', 'tuner', lambda features, main: 'tuner' in features),
    _Block('dsp', 'dsp', lambda features, main: 'sound_program' in main),
    _Block('zone2', 'zone2', _has_zone('zone2')),
    _Block('zone3', 'zone3', _has_zone('zone3')),
    _Block('zone4', 'zone4', _has_zone('zone4')),
    _Block('alarm', None, lambda features, main: 'alarm' in features.get('clock', {}).get('func_list', [])),
)
_ZONE_STRUCTS = ('zone2', 'zone3', 'zone4')
_WIDGET_ORDER = ('dsp', 'netusb', 'link', 'tuner', 'zone2', 'zone3', 'zone4')


def recommend(features: dict) -> StructAdvice:
    """derive the structs to combine for a device: amp always, the rest by what getFeatures reports"""
    main = _main_funcs(features)
    present = [block for block in _BLOCKS if block.present(features, main)]
    widgets = {block.widget for block in present if block.widget}
    return StructAdvice(tuple(block.struct for block in present), tuple(key for key in _WIDGET_ORDER if key in widgets))


def ready_made(model_name: str, known_structs: set[str]) -> str | None:
    """the plugin's device struct named after the model (lowercased), None if there is none"""
    name = model_name.lower()
    return name if name in known_structs else None


def render_config(host: str, advice: StructAdvice, device_struct: str | None) -> str:
    """
    item yaml for a device: its ready-made struct if given, else the recommended building blocks

    Extra zones are not part of the device item's struct list: their struct fills a child item named
    after the zone, so each of them gets one.
    """
    if device_struct:
        return f'device:\n    yamahayxc_host: {host}\n    struct: yamahayxc.{device_struct}\n'
    blocks = [name for name in advice.structs if name not in _ZONE_STRUCTS]
    struct = '[' + ', '.join(f'yamahayxc.{name}' for name in blocks) + ']'
    zones = ''.join(
        f'    {name}:\n        struct: yamahayxc.{name}\n' for name in advice.structs if name in _ZONE_STRUCTS
    )
    return f'device:\n    yamahayxc_host: {host}\n    struct: {struct}\n{zones}'
