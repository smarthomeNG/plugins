"""
json_tree: mirror a JSON payload as an item tree whose leaves select their part via mqtt_select_in.

Pure functions, no mocks.
"""

import unittest

import jmespath

from plugins.mqtt.json_tree import build_item_tree, leaf_paths, parse_json_value, sanitize_item_name


def _leaves(tree, prefix=''):
    """Yield (item path, leaf conf) for all leaves (items carrying mqtt_select_in) of a tree."""
    for name, node in tree.items():
        if 'mqtt_select_in' in node:
            yield prefix + name, node
        for child, value in node.items():
            if isinstance(value, dict):
                yield from _leaves({child: value}, prefix + name + '.')


class TestBuildItemTree(unittest.TestCase):
    def test_flat_dict_infers_types(self):
        tree = build_item_tree({'temp': 21.5, 'count': 3, 'on': True, 'name': 'abc'})
        self.assertEqual(
            tree,
            {
                'temp': {'type': 'num', 'mqtt_select_in': 'temp'},
                'count': {'type': 'num', 'mqtt_select_in': 'count'},
                'on': {'type': 'bool', 'mqtt_select_in': 'on'},
                'name': {'type': 'str', 'mqtt_select_in': 'name'},
            },
        )

    def test_nested_dict_becomes_branch_without_select(self):
        tree = build_item_tree({'state': {'on': True, 'level': 7}})
        self.assertEqual(
            tree,
            {
                'state': {
                    'on': {'type': 'bool', 'mqtt_select_in': 'state.on'},
                    'level': {'type': 'num', 'mqtt_select_in': 'state.level'},
                }
            },
        )

    def test_list_elements_become_indexed_items(self):
        tree = build_item_tree({'sensors': [{'v': 1}, {'v': 2}]})
        self.assertEqual(tree['sensors']['item_1']['v'], {'type': 'num', 'mqtt_select_in': 'sensors[1].v'})

    def test_root_list(self):
        tree = build_item_tree([5, 6])
        self.assertEqual(tree['item_0'], {'type': 'num', 'mqtt_select_in': '[0]'})
        self.assertEqual(tree['item_1'], {'type': 'num', 'mqtt_select_in': '[1]'})

    def test_empty_containers_and_null_are_leaves(self):
        tree = build_item_tree({'d': {}, 'l': [], 'n': None})
        self.assertEqual(tree['d'], {'type': 'dict', 'mqtt_select_in': 'd'})
        self.assertEqual(tree['l'], {'type': 'list', 'mqtt_select_in': 'l'})
        self.assertEqual(tree['n'], {'type': 'str', 'mqtt_select_in': 'n'})

    def test_odd_keys_are_sanitized_and_selected_quoted(self):
        tree = build_item_tree({'a-b': 1, '0x': 2})
        self.assertEqual(tree['a_b'], {'type': 'num', 'mqtt_select_in': '"a-b"'})
        self.assertEqual(tree['n_0x'], {'type': 'num', 'mqtt_select_in': '"0x"'})

    def test_colliding_names_stay_unique(self):
        tree = build_item_tree({'a-b': 1, 'a_b': 2})
        self.assertEqual(sorted(tree), ['a_b', 'a_b_'])
        self.assertEqual(tree['a_b']['mqtt_select_in'], '"a-b"')
        self.assertEqual(tree['a_b_']['mqtt_select_in'], 'a_b')

    def test_reserved_names_are_avoided(self):
        tree = build_item_tree({'get': 1, 'class': 2, 'comment_x': 3, 'type': 4}, is_reserved=lambda n: n == 'type')
        self.assertEqual(sorted(tree), ['class_', 'get_', 'n_comment_x', 'type_'])

    def test_every_leaf_selects_its_value_with_jmespath(self):
        payload = {
            'a-b': {'c d': [1, {'x"y': 'z'}]},
            'plain': {'deep': {'deeper': 2.5}},
            'list': [[1, 2], [3]],
            'ünï': True,
        }
        leaves = list(_leaves(build_item_tree(payload)))
        self.assertEqual(len(leaves), 7)
        for _, conf in leaves:
            value = jmespath.search(conf['mqtt_select_in'], payload)
            expected = {'num': (int, float), 'bool': (bool,), 'str': (str,)}[conf['type']]
            self.assertIsInstance(value, expected)


class TestParseJsonValue(unittest.TestCase):
    def test_dict_and_list_pass_through(self):
        self.assertEqual(parse_json_value({'a': 1}), {'a': 1})
        self.assertEqual(parse_json_value([1]), [1])

    def test_json_string_is_parsed(self):
        self.assertEqual(parse_json_value('{"a": 1}'), {'a': 1})

    def test_rejects_non_json_and_scalars(self):
        for value in ('not json', '42', '"str"', 42, None, ''):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    parse_json_value(value)


class TestHelpers(unittest.TestCase):
    def test_leaf_paths_lists_the_leaves_below_the_base_path(self):
        tree = build_item_tree({'t': 1, 'o': {'on': True}, 'l': [1], 'e': {}})

        self.assertEqual(sorted(leaf_paths('a.b', tree)), ['a.b.e', 'a.b.l.item_0', 'a.b.o.on', 'a.b.t'])

    def test_sanitize_plain_name_unchanged(self):
        self.assertEqual(sanitize_item_name('temp_1'), 'temp_1')


if __name__ == '__main__':
    unittest.main()
