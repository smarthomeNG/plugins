#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2014-     Thomas Ernst                       offline@gmx.net
#########################################################################
#  Finite state machine plugin for SmartHomeNG
#
#  This plugin is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This plugin is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this plugin. If not, see <http://www.gnu.org/licenses/>.
#########################################################################

import re
from collections import OrderedDict
from . import StateEngineTools
try:
    import pydotplus
    REQUIRED_PACKAGE_IMPORTED = True
except Exception:
    REQUIRED_PACKAGE_IMPORTED = False


# Class representing a value for a condition (either value or via item/eval)
class WebInterface(StateEngineTools.SeItemChild):
    # Constructor
    # abitem: parent SeItem instance
    def __init__(self, smarthome, abitem):
        super().__init__(abitem)

        if not REQUIRED_PACKAGE_IMPORTED:
            self._log_warning("Unable to import Python package 'pydotplus'. Visualizing SE items will not work.")

        self.__states = abitem.webif_infos
        self.__name = abitem.id
        self.__active_conditionset = abitem.lastconditionset_name
        self.__active_state = abitem.laststate

        self.__graph = pydotplus.Dot('StateEngine', graph_type='digraph', splines='false',
                                     overlap='scale', compound='false')
        self.__graph.set_node_defaults(color='lightgray', style='filled', shape='box',
                                       fontname='Helvetica', fontsize='10')
        self.__graph.set_edge_defaults(color='darkgray', style='filled', shape='box',
                                       fontname='Helvetica', fontsize='10')
        self.__nodes = {}
        self.__scalefactor = 0.1
        self.__textlimit = 145
        self.__conditionset_count = 0

    def __repr__(self):
        return "WebInterface item: {}, id {}.".format(self.__states, self.__name) if REQUIRED_PACKAGE_IMPORTED else "None"

    def _actionlabel(self, state, label_type, conditionset, label_format='table'):
        actionlabel = '<<table border="0">' if label_format == 'table' else '<'
        originaltype = label_type
        types = [label_type] if label_type == 'actions_leave' else ['actions_enter_or_stay', label_type]
        for label_type in types:
            for action in self.__states[state].get(label_type):
                condition_to_meet = self.__states[state][label_type][action].get('conditionset')
                condition_to_meet = StateEngineTools.flatten_list(condition_to_meet)
                condition_met = True if condition_to_meet == 'None' else False
                condition_to_meet = condition_to_meet if isinstance(condition_to_meet, list) else [condition_to_meet]
                _repeat = self.__states[state][label_type][action].get('repeat')
                _delay = self.__states[state][label_type][action].get('delay') or 0
                for cond in condition_to_meet:
                    try:
                        cond = re.compile(cond)
                        matching = cond.fullmatch(conditionset)
                    except Exception:
                        matching = True
                    condition_met = True if matching else condition_met
                fontcolor = "white" if not condition_met or (_repeat is False and originaltype == 'actions_stay')\
                            else "#5c5646" if _delay > 0 else "darkred" if _delay < 0 else "black"
                additionaltext = " ({} not met)".format(condition_to_meet) if not condition_met\
                                 else " (no repeat)" if _repeat is False and originaltype == 'actions_stay'\
                                 else " (delay: {})".format(_delay) if _delay > 0\
                                 else " (wrong delay!)" if _delay < 0 else ""
                action1 = self.__states[state][label_type][action].get('function')
                if action1 == 'set':
                    action2 = self.__states[state][label_type][action].get('item')
                    value_check = self.__states[state][label_type][action].get('value')
                    value_check = '""' if value_check == "" else value_check
                    action3 = 'to {}'.format(value_check)
                elif action1 == 'special':
                    action2 = self.__states[state][label_type][action].get('special')
                    action3 = self.__states[state][label_type][action].get('value')
                else:
                    action2 = 'None'
                    action3 = ''
                if label_format == 'table' and not action2 == 'None':
                    actionlabel += '<tr><td align="center"><font color={}>{}</font></td><td align="center">{}</td>' \
                                   '<td align="center">{}</td></tr>'.format(fontcolor, action1, action2, action3)
                elif not action2 == 'None':
                    actionlabel += '<font color="{}">&nbsp;&nbsp;{} {} {}{}&nbsp;&nbsp;</font><br />'.format(
                        fontcolor, action1, action2, action3, additionaltext)
        actionlabel += '</table>>' if label_format == 'table' else '>'
        actionlabel = '' if actionlabel == '<<table border="0"></table>>' or actionlabel == '<>' else actionlabel
        #self._log_debug('actionlabel: {}', actionlabel)
        return actionlabel

    def _conditionlabel(self, state, conditionset):
        condition_tooltip = ''
        _empty_set = self.__states[state]['conditionsets'].get(conditionset) == ''
        if _empty_set:
            return '', ''
        conditionlist = '<<table border="0" cellpadding="5">'

        for k, condition in enumerate(self.__states[state]['conditionsets'].get(conditionset)):
            condition_dict = self.__states[state]['conditionsets'][conditionset].get(condition)
            item_none = condition_dict.get('item') == 'None'
            eval_none = condition_dict.get('eval') == 'None'
            value_none = condition_dict.get('value') == 'None'
            min_none = condition_dict.get('min') == 'None'
            max_none = condition_dict.get('max') == 'None'
            agemin_none = condition_dict.get('agemin') == 'None'
            agemax_none = condition_dict.get('agemax') == 'None'
            changedby_none = condition_dict.get('changedby') == 'None'
            updatedby_none = condition_dict.get('updatedby') == 'None'

            for compare in condition_dict:
                cond1 = not condition_dict.get(compare) == 'None'
                cond2 = not compare == 'item'
                cond3 = not compare == 'eval'
                cond4 = not compare == 'negate'
                cond5 = not compare == 'agenegate'
                cond6 = not compare == 'changedbynegate'
                cond7 = not compare == 'updatedbynegate'
                if cond1 and cond2 and cond3 and cond4 and cond5 and cond6 and cond7:
                    conditionlist += '<tr><td align="center"><b>'
                    textlength = len(str(condition_dict.get('item')))
                    condition_tooltip += '{}&#13;&#10;&#13;&#10;'.format(condition_dict.get('item')) \
                        if textlength > self.__textlimit else ''
                    info = str(condition_dict.get('item'))[:self.__textlimit] + '.. &nbsp;' * (textlength > self.__textlimit)
                    conditionlist += '{}'.format(info) if not item_none else ''
                    textlength = len(str(condition_dict.get('eval')))
                    condition_tooltip += '{}&#13;&#10;&#13;&#10;'.format(condition_dict.get('eval')) \
                        if textlength > self.__textlimit else ''
                    info = str(condition_dict.get('eval'))[:self.__textlimit] + '.. &nbsp;' * (textlength > self.__textlimit)
                    conditionlist += '{}'.format(info) if not eval_none and item_none else ''
                    conditionlist += '</b></td>'
                    comparison = "&#62;=" if not min_none and compare == "min"\
                                 else "&#60;=" if not max_none and compare == "max"\
                                 else "older" if not agemin_none and compare == "agemin"\
                                 else "younger" if not agemax_none and compare == "agemax"\
                                 else "not changed by" if (not changedby_none and compare == "changedby"
                                                           and condition_dict.get('changedbynegate') == 'True')\
                                 else "changed by" if not changedby_none and compare == "changedby"\
                                 else "not updated by" if (not updatedby_none and compare == "updatedby"
                                                           and condition_dict.get('updatedbynegate') == 'True')\
                                 else "updated by" if not updatedby_none and compare == "updatedby"\
                                 else "!=" if (not value_none and compare == "value"
                                               and condition_dict.get('negate') == 'True')\
                                 else "=="
                    conditionlist += '<td align="center" width="5">{}</td><td align="center">'.format(comparison)
                    conditionlist += '"{}"'.format(info) if not item_none and not eval_none else ''
                    textlength = len(str(condition_dict.get(compare)))
                    condition_tooltip += '{}&#13;&#10;&#13;&#10;'.format(condition_dict.get(compare)) \
                        if textlength > self.__textlimit else ''
                    info = str(condition_dict.get(compare))[:self.__textlimit] + '.. &nbsp;' * \
                        (len(str(condition_dict.get(compare))) > self.__textlimit)
                    conditionlist += '{}'.format(info) if not condition_dict.get(compare) == 'None' and (
                                     (eval_none and not item_none) or (not eval_none and item_none)) else ''
                    conditionlist += ' (negate)' if condition_dict.get('negate') == 'True' and "age" \
                                     not in compare and not compare == "value" else ''
                    conditionlist += ' (negate)' if condition_dict.get('agenegate') == 'True' and "age" in compare else ''
                    conditionlist += '</td></tr>'
        conditionlist += '<tr><td></td><td></td><td></td></tr></table>>'
        return conditionlist, condition_tooltip

    def _add_actioncondition(self, state, conditionset, action_type, new_y, cond1, cond2):
        cond4 = conditionset in ['', self.__active_conditionset] and state == self.__active_state
        cond5 = self.__states[state]['conditionsets'].get(conditionset) is not None
        cond_enter = action_type == 'actions_enter' and self.__states[state].get('enter') is False
        cond_stay = action_type == 'actions_stay' and self.__states[state].get('stay') is False
        color_enter = "gray" if (cond1 and cond2 and cond5) or \
                                (cond_enter and cond4 and cond5) else "chartreuse3" if cond4 else "indianred2"
        color_stay = "gray" if (cond1 and cond2 and cond5) or \
                               (cond_stay and cond4 and cond5) else "chartreuse3" if cond4 else "indianred2"

        label = 'first enter' if action_type == 'actions_enter' else 'staying at state'

        position = '{},{}!'.format(0.63, new_y)
        color = color_enter if label == 'first enter' else color_stay
        self.__nodes['{}_{}_state_{}'.format(state, conditionset, action_type)] = \
            pydotplus.Node('{}_{}_state_{}'.format(state, conditionset, action_type), style="filled", fillcolor=color,
                           shape="diamond", label=label, pos=position)
        self.__graph.add_node(self.__nodes['{}_{}_state_{}'.format(state, conditionset, action_type)])
        if self.__nodes.get('{}_{}_state_actions_enter_edge'.format(state, conditionset)) is None:
            self.__nodes['{}_{}_state_{}_edge'.format(state, conditionset, action_type)] = \
                pydotplus.Edge(self.__nodes['{}_{}'.format(state, conditionset)], self.__nodes['{}_{}_state_{}'.format(
                    state, conditionset, action_type)], style='bold', taillabel="    True", tooltip='first enter')
            self.__graph.add_edge(self.__nodes['{}_{}_state_{}_edge'.format(state, conditionset, action_type)])
        else:
            self.__graph.add_edge(pydotplus.Edge(self.__nodes['{}_{}_state_actions_enter'.format(state, conditionset)],
                                                 self.__nodes['{}_{}_state_actions_stay'.format(state, conditionset)],
                                                 style='bold', label="False    "))
        self.__graph.add_edge(pydotplus.Edge(self.__nodes['{}_{}_state_{}'.format(state, conditionset, action_type)],
                                             self.__nodes['{}_{}_{}'.format(state, conditionset, action_type)],
                                             style='bold', taillabel="    True"))
        try:
            if action_type == 'actions_enter':
                self.__nodes['{}_{}_actions_enter'.format(state, conditionset)].obj_dict['attributes']['fillcolor'] = color
        except Exception:
            pass
        try:
            if action_type == 'actions_stay':
                self.__nodes['{}_{}_actions_stay'.format(state, conditionset)].obj_dict['attributes']['fillcolor'] = color
        except Exception:
            pass

    def drawgraph(self, filename):
        new_y = 2
        previous_state = ''
        previous_conditionset = ''
        #self._log_debug('STATES {}', self.__states)
        for i, state in enumerate(self.__states):
            #self._log_debug('Adding state for webif {}', self.__states[state])
            if isinstance(self.__states[state], (OrderedDict, dict)):
                self.__conditionset_count = len(self.__states[state].get('conditionsets'))
                if self.__conditionset_count == 0:
                    self.__states[state]['conditionsets'][''] = ''
                color = "chartreuse3" if state == self.__active_state \
                    else "gray" if i > list(self.__states.keys()).index(self.__active_state) else "indianred2"

                new_y -= 1 * self.__scalefactor
                position = '{},{}!'.format(0, new_y)
                if not i == 0:
                    condition_node = 'leave' if self.__nodes.get('{}_leave'.format(previous_state)) \
                        else list(self.__states[previous_state]['conditionsets'].keys())[-1]
                    lastnode = self.__nodes['{}_{}'.format(previous_state, condition_node)]
                    self.__nodes['{}_above'.format(state)] = pydotplus.Node('{}_above'.format(state), pos=position,
                                                                            shape="square", width="0", label="")
                    self.__graph.add_node(self.__nodes['{}_above'.format(state)])
                    position = '{},{}!'.format(0.5, new_y)
                    self.__nodes['{}_above_right'.format(state)] = pydotplus.Node('{}_above_right'.format(state),
                                                                                  pos=position, shape="square", width="0", label="")
                    self.__graph.add_node(self.__nodes['{}_above_right'.format(state)])
                    self.__graph.add_edge(pydotplus.Edge(self.__nodes['{}_above'.format(state)],
                                                         self.__nodes['{}_above_right'.format(state)], style='bold',
                                                         color='black', label="", dir="none"))
                    self.__graph.add_edge(pydotplus.Edge(self.__nodes['{}_above_right'.format(state)], lastnode,
                                                         style='bold', color='black', label="False   ", dir="none"))
                    self.__graph.add_edge(pydotplus.Edge(state, self.__nodes['{}_above'.format(state)], style='bold',
                                                         color='black', label="", dir="back"))
                new_y -= 1 * self.__scalefactor
                position = '{},{}!'.format(0, new_y)
                #self._log_debug('state: {} {}',state, position)
                self.__nodes[state] = pydotplus.Node(state, pos=position, pin=True, notranslate=True, style="filled",
                                                     fillcolor=color, shape="ellipse",
                                                     label='<<table border="0"><tr><td>{}</td></tr><hr/><tr>'
                                                           '<td>{}</td></tr></table>>'.format(state, self.__states[state]['name']))
                position = '{},{}!'.format(0.5, new_y)
                self.__nodes['{}_right'.format(state)] = pydotplus.Node('{}_right'.format(state), pos=position,
                                                                        shape="square", width="0", label="")
                self.__graph.add_node(self.__nodes[state])
                self.__graph.add_node(self.__nodes['{}_right'.format(state)])
                conditionset_positions = []
                actionlist_enter = ''
                actionlist_stay = ''
                actionlist_leave = ''
                condition_tooltip = ''
                j = 0
                new_x = 0.9
                for j, conditionset in enumerate(self.__states[state]['conditionsets']):
                    if len(self.__states[state].get('actions_enter')) > 0 or len(self.__states[state].get('actions_enter_or_stay')) > 0:
                        actionlist_enter = self._actionlabel(state, 'actions_enter', conditionset, 'list')

                    if len(self.__states[state].get('actions_stay')) > 0 or len(self.__states[state].get('actions_enter_or_stay')) > 0:
                        actionlist_stay = self._actionlabel(state, 'actions_stay', conditionset, 'list')

                    if len(self.__states[state].get('actions_leave')) > 0:
                        actionlist_leave = self._actionlabel(state, 'actions_leave', conditionset, 'list')

                    new_y -= 1 * self.__scalefactor if j == 0 else 2 * self.__scalefactor
                    position = '{},{}!'.format(0.5, new_y)
                    conditionset_positions.append(new_y)
                    #self._log_debug('conditionset: {} {}, previous {}', conditionset, position, previous_conditionset)

                    conditionlist, condition_tooltip = self._conditionlabel(state, conditionset)
                    cond3 = conditionset == ''
                    try:
                        cond1 = i >= list(self.__states.keys()).index(self.__active_state)
                    except Exception as ex:
                        #self._log_debug('Condition 1 problem {}'.format(ex))
                        cond1 = True
                    try:
                        cond4 = i == list(self.__states.keys()).index(self.__active_state)
                    except Exception as ex:
                        #self._log_debug('Condition 4 problem {}'.format(ex))
                        cond4 = True
                    #self._log_debug('i {}, index of active state {}', i, list(self.__states.keys()).index(self.__active_state))
                    try:
                        cond2 = (j > list(self.__states[state]['conditionsets'].keys()).index(self.__active_conditionset)
                                 or i > list(self.__states.keys()).index(self.__active_state))
                    except Exception as ex:
                        #self._log_debug('Condition 2 problem {}'.format(ex))
                        cond2 = False if cond3 and cond4 else True
                    color = "gray" if cond1 and cond2 else "chartreuse3" \
                        if (conditionset == self.__active_conditionset or cond3) and state == self.__active_state else "indianred2"
                    label = 'no condition' if conditionset == '' else conditionset
                    self.__nodes['{}_{}'.format(state, conditionset)] = pydotplus.Node(
                        '{}_{}'.format(state, conditionset), style="filled", fillcolor=color, shape="diamond",
                        label=label, pos=position)
                    #self._log_debug('Node {} {} drawn', state, conditionset)
                    position = '{},{}!'.format(0.2, new_y)
                    if not conditionlist == '':
                        self.__nodes['{}_{}_conditions'.format(state, conditionset)] = pydotplus.Node(
                            '{}_{}_conditions'.format(state, conditionset), style="filled", fillcolor=color,
                            shape="rect", label=conditionlist, pos=position, tooltip=condition_tooltip)
                        self.__graph.add_node(self.__nodes['{}_{}_conditions'.format(state, conditionset)])

                    self.__graph.add_node(self.__nodes['{}_{}'.format(state, conditionset)])

                    new_x = 0.9
                    if not actionlist_enter == '':
                        position = '{},{}!'.format(new_x, new_y)
                        #self._log_debug('action enter: {}', position)
                        self.__nodes['{}_{}_actions_enter'.format(state, conditionset)] = pydotplus.Node(
                            '{}_{}_actions_enter'.format(state, conditionset), style="filled", fillcolor=color,
                            shape="rectangle", label=actionlist_enter, pos=position)
                        self.__graph.add_node(self.__nodes['{}_{}_actions_enter'.format(state, conditionset)])
                        self._add_actioncondition(state, conditionset, 'actions_enter', new_y, cond1, cond2)

                    if not actionlist_stay == '':
                        new_y -= 0.05 if not actionlist_enter == '' else 0
                        position = '{},{}!'.format(new_x, new_y)
                        #self._log_debug('action stay: {}', position)
                        self.__nodes['{}_{}_actions_stay'.format(state, conditionset)] = pydotplus.Node(
                            '{}_{}_actions_stay'.format(state, conditionset), style="filled", fillcolor=color,
                            shape="rectangle", label=actionlist_stay, pos=position)
                        self.__graph.add_node(self.__nodes['{}_{}_actions_stay'.format(state, conditionset)])
                        self._add_actioncondition(state, conditionset, 'actions_stay', new_y, cond1, cond2)

                    position = '{},{}!'.format(0.9, new_y)
                    cond1 = self.__nodes.get('{}_{}_actions_enter'.format(state, conditionset)) is None
                    cond2 = self.__nodes.get('{}_{}_actions_stay'.format(state, conditionset)) is None
                    cond3 = self.__nodes.get('{}_{}_actions_leave'.format(state, conditionset)) is None
                    if cond1 and cond2 and cond3:
                        self.__nodes['{}_{}_right'.format(state, conditionset)] = pydotplus.Node('{}_{}_right'.format(
                            state, conditionset), shape="circle", width="0.7", pos=position, label="", fillcolor="black",
                            style="filled", tooltip="No Action")
                        self.__graph.add_node(self.__nodes['{}_{}_right'.format(state, conditionset)])
                        self.__graph.add_edge(pydotplus.Edge(self.__nodes['{}_{}'.format(state, conditionset)],
                                                             self.__nodes['{}_{}_right'.format(state, conditionset)],
                                                             style='bold', taillabel="    True", tooltip='action on enter'))

                    if j == 0:
                        self.__graph.add_edge(pydotplus.Edge(self.__nodes[state], self.__nodes['{}_right'.format(state)],
                                                             style='bold', color='black', dir='none',
                                                             edgetooltip='check first conditionset'))
                        self.__graph.add_edge(pydotplus.Edge(self.__nodes['{}_right'.format(state)],
                                                             self.__nodes['{}_{}'.format(state, conditionset)],
                                                             style='bold', color='black', tooltip='check first conditionset'))
                        #self._log_debug('Drew line from state')
                    else:
                        self.__graph.add_edge(pydotplus.Edge(previous_conditionset,
                                                             self.__nodes['{}_{}'.format(state, conditionset)],
                                                             style='bold', color='black', tooltip='check next conditionset'))
                    previous_conditionset = self.__nodes['{}_{}'.format(state, conditionset)]

                if len(self.__states[state].get('actions_leave')) > 0:
                    new_y -= 1 * self.__scalefactor if j == 0 else 2 * self.__scalefactor
                    position = '{},{}!'.format(0.5, new_y)
                    #self._log_debug('leaveconditions {}', position)
                    try:
                        cond1 = j > list(self.__states[state]['conditionsets'].keys()).index(self.__active_conditionset)
                    except Exception:
                        cond1 = True
                    try:
                        cond2 = i >= list(self.__states.keys()).index(self.__active_state)
                    except Exception:
                        cond2 = True
                    cond3 = True if self.__states[state].get('leave') is True else False
                    color = "gray" if cond1 and cond2 and not cond3 else "chartreuse3" if cond3 else "indianred2"
                    self.__nodes['{}_leave'.format(state)] = pydotplus.Node('{}_leave'.format(state),
                                                                            style="filled", fillcolor=color, shape="diamond",
                                                                            label='leave', pos=position)
                    self.__graph.add_node(self.__nodes['{}_leave'.format(state)])
                    self.__graph.add_edge(pydotplus.Edge(previous_conditionset, self.__nodes['{}_leave'.format(state)],
                                                         style='bold', color='black', tooltip='check leave'))

                    position = '{},{}!'.format(new_x, new_y)
                    #self._log_debug('action leave: {}', position)
                    self.__nodes['{}_actions_leave'.format(state)] = pydotplus.Node('{}_actions_leave'.format(state),
                                                                                    style="filled", fillcolor=color,
                                                                                    shape="rectangle", label=actionlist_leave,
                                                                                    pos=position, align="center")
                    self.__graph.add_node(self.__nodes['{}_actions_leave'.format(state)])
                    self.__graph.add_edge(pydotplus.Edge(self.__nodes['{}_leave'.format(state)],
                                                         self.__nodes['{}_actions_leave'.format(state)], style='bold',
                                                         taillabel="    True", tooltip='run leave actions'))

                previous_state = state

        result = self.__graph.write_svg(filename, prog='fdp')
        return result
