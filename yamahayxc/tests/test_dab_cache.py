"""StationCache: service names learned from the tuner, the walked service list, and when both go stale."""

from plugins.yamahayxc.dabstations import DabPlayInfo, DabService, StationCache


def test_observed_service_names_are_remembered_trimmed():
    cache = StationCache()

    cache.observe(DabPlayInfo(7, 'Dlf             ', 102))

    assert cache.name_of(7) == 'Dlf'
    assert cache.name_of(8) == ''


def test_a_published_walk_is_kept_in_order_and_teaches_the_names():
    cache = StationCache()
    walked = (DabService(3, 'RADIO BOB!'), DabService(9, 'WDR 2'))

    cache.publish(walked, total=2)

    assert cache.services == walked
    assert cache.name_of(9) == 'WDR 2'


def test_a_changed_station_count_drops_the_list_and_the_names():
    cache = StationCache()
    cache.publish((DabService(3, 'RADIO BOB!'),), total=102)
    cache.observe(DabPlayInfo(3, 'RADIO BOB!', 102))

    cache.observe(DabPlayInfo(7, 'Dlf', 27))

    assert cache.services == ()
    assert cache.name_of(3) == ''
    assert cache.name_of(7) == 'Dlf'


def test_a_service_whose_label_is_still_empty_is_not_remembered():
    cache = StationCache()

    cache.observe(DabPlayInfo(7, '        ', 102))

    assert cache.name_of(7) == ''


def test_invalidate_drops_the_list_and_the_names():
    cache = StationCache()
    cache.publish((DabService(3, 'RADIO BOB!'),), total=102)

    cache.invalidate()

    assert cache.services == ()
    assert cache.name_of(3) == ''


def test_names_learned_without_a_walk_are_dropped_when_the_count_changes_too():
    cache = StationCache()
    cache.observe(DabPlayInfo(3, 'RADIO BOB!', 102))

    cache.observe(DabPlayInfo(7, 'Dlf', 27))

    assert cache.name_of(3) == ''
