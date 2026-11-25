import pytest

from .test_plugin import make_plugin

MARKED = {'house', 'house.living.lamp', 'house.alarm', 'house.garage', 'typo'}


def items_of(plugin):
    return {item.property.path: item for item in plugin._smarthome.items.return_items()}


def bind_all(plugin):
    """Do what core does for every item: bind it and register the update method the plugin returns."""
    for item in plugin._smarthome.items.return_items():
        update = plugin.parse_item(item)
        if update:
            item.add_method_trigger(update)


@pytest.fixture
def plugin():
    plugin = make_plugin()
    yield plugin
    plugin.stop()


def test_items_with_an_explicit_access_attribute_are_bound_to_the_plugin(plugin):
    bind_all(plugin)
    assert set(plugin.get_item_path_list()) == MARKED


def test_items_without_the_attribute_are_not_bound_even_below_a_marked_parent(plugin):
    bind_all(plugin)
    assert not {'house.living.temp', 'house.garage.door', 'unmarked'} & set(plugin.get_item_path_list())


def test_removing_an_item_unbinds_it_and_keeps_the_server_running(plugin):
    bind_all(plugin)
    plugin.run()
    assert plugin.alive
    assert plugin.remove_item(items_of(plugin)['house.garage'])
    assert 'house.garage' not in plugin.get_item_path_list()
    assert plugin.alive


def test_only_bound_items_return_an_update_method(plugin):
    items = items_of(plugin)
    assert plugin.parse_item(items['house.garage']) == plugin.update_item
    assert plugin.parse_item(items['house.living.temp']) is None
