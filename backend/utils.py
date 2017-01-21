#!/usr/bin/env python3
# -*- coding: utf8 -*-
#########################################################################
#  Copyright 2016 Bernd Meiners,
#                 Christian Strassburg            c.strassburg@gmx.de
#                 René Frieß                      rene.friess@gmail.com
#                 Martin Sinn                     m.sinn@gmx.de
#########################################################################
#  Backend plugin for SmartHomeNG
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

import logging
import json
import os
import collections
from collections import OrderedDict
import ruamel.yaml as yaml


# Funktionen für Jinja2 z.Zt außerhalb der Klasse Backend, da ich Jinja2 noch nicht mit
# Methoden einer Klasse zum laufen bekam


def get_basename(p):
    """
    returns the filename of a full pathname

    This function extends the jinja2 template engine
    """
    return os.path.basename(p)


def is_userlogic(sh, logic):
    """
    returns True if userlogic and False if system logic
    
    This function extends the jinja2 template engine
    """
    return os.path.basename(os.path.dirname(sh.return_logic(logic).filename)) == 'logics'
    
    
translation_dict = {}
translation_lang = ''


def get_translation_lang():
    global translation_lang
    return translation_lang


def load_translation(language):
    global translation_dict    # Needed to modify global copy of translation_dict
    global translation_lang    # Needed to modify global copy of translation_lang
    
    logger = logging.getLogger(__name__)
    
    translation_lang = language.lower()
    if translation_lang == '':
        translation_dict = {}
    else:
        lang_filename = os.path.dirname(os.path.abspath(__file__))+'/locale/' + translation_lang + '.json'
        try:
            f=open(lang_filename,'r')
        except:
            translation_lang = ''
            return False
        try:
            translation_dict=json.load(f)
        except Exception as e:
            logger.error("Backend: load_translation language='{0}': Error '{1}'".format(translation_lang, e))
            return False
    logger.debug("Backend: translation_dict='{0}'".format(translation_dict))
    return True


def html_escape(str):
    str = str.rstrip().replace('<','&lt;').replace('>','&gt;')
    str = str.rstrip().replace('(','&#40;').replace(')','&#41;')
    html = str.rstrip().replace("'",'&#39;').replace('"','&quot;')
    return html


def translate(txt, block=''):
    """
    returns translated text
    
    This function extends the jinja2 template engine
    """
    logger = logging.getLogger(__name__)

    txt = str(txt)
    if translation_lang == '':
        tr = txt
    else:
        if block != '':
            blockdict = translation_dict.get('_'+block,{})
            tr = blockdict.get(txt,'')
            if tr == '':
                tr = translation_dict.get(txt,'')
        else:
            tr = translation_dict.get(txt,'')
        if tr == '':
            logger.warning("Backend: Language '{0}': Translation for '{1}' is missing".format(translation_lang, txt))
            tr = txt
    return html_escape(tr)


def create_hash(plaintext):
    import hashlib
    hashfunc = hashlib.sha512()
    hashfunc.update(plaintext.encode())
    return hashfunc.hexdigest()


def parse_requirements(file_path):
    fobj = open(file_path)
    req_dict = {}
    for line in fobj:
        if len(line) > 0 and '#' not in line:
            if ">" in line:
                if line[0:line.find(">")].lower().strip() in req_dict:
                    req_dict[line[0:line.find(">")].lower().strip()] += " | "+line[line.find(">"):len(line)].lower().strip()
                else:
                    req_dict[line[0:line.find(">")].lower().strip()] = line[line.find(">"):len(line)].lower().strip()
            elif "<" in line:
                if line[0:line.find("<")].lower().strip() in req_dict:
                    req_dict[line[0:line.find("<")].lower().strip()] += " | "+line[line.find("<"):len(line)].lower().strip()
                else:
                    req_dict[line[0:line.find("<")].lower().strip()] = line[line.find("<"):len(line)].lower().strip()
            elif "=" in line:
                if line[0:line.find("=")].lower().strip() in req_dict:
                    req_dict[line[0:line.find("=")].lower().strip()] += " | "+line[line.find("="):len(line)].lower().strip()
                else:
                    req_dict[line[0:line.find("=")].lower().strip()] = line[line.find("="):len(line)].lower().strip()
    fobj.close()
    return req_dict

def strip_quotes(string):
    string = string.strip()
    if string[0] in ['"', "'"]:  # check if string starts with ' or "
        if string[0] == string[-1]:  # and end with it
            if string.count(string[0]) == 2:  # if they are the only one
                string = string[1:-1]  # remove them
    return string

def handle_multiline_string(string):
    if len(string) > 0 and string.find('\n') > -1 and string[0] != '|':
        string = '|\n' + string
    return string

def parse_for_convert(conf_code, config=None):
    valid_chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_@*'
    valid_set = set(valid_chars)
    if config is None:
        config = collections.OrderedDict()
    item = config
    lastline_was_comment = False
    last_comment_nr = 0
    linenu = 0
    parent = collections.OrderedDict()
    lines = conf_code.splitlines()
    for line in lines:
        linenu += 1
        line = line.lstrip('\ufeff')  # remove BOM

        multiline = []
        if line.rstrip().endswith('\\'):
            i = 0
            while line.rstrip().endswith('\\'):
                multiline.append(line.rstrip().rstrip('\\').strip())
                i += 1
                linenu += 1
                line = next(lines, '').lstrip()
            line = '\n'.join(multiline) + '\n' + line.strip()
            lastline_was_comment = False
        if (len(multiline) == 0) or (line[0] == '#'):
            if len(multiline) == 0:
                comment_in_line = line.find('#')
                comment = line.partition('#')[2].strip()
                if comment_in_line > -1 and comment == '':
                    comment = '>**<'
                line = line.partition('#')[0].strip()
                # inline comment
                if (line != '') and (comment != '') and line.find('[') == -1:
                    attr, __, value = line.partition('=')
                    comment = attr.strip() + ': ' + comment
                    line = line + '    ## ' + comment
                    comment = ''
            else:
                comment = line
                line = ''
            if comment != '':
                while (comment != '') and (comment[0] == '#'):
                    comment = comment[1:].strip()
            if comment != '':
                comment = comment.replace('\t', ' ')
                if 'comment' in item.keys():
                    if lastline_was_comment:
                        if last_comment_nr > 0:
                            item['comment' + str(last_comment_nr)] = handle_multiline_string(
                                item['comment' + str(last_comment_nr)] + '\n' + strip_quotes(comment))
                        else:
                            item['comment'] = handle_multiline_string(
                                item['comment'] + '\n' + strip_quotes(comment))
                    else:
                        i = 1
                        while 'comment' + str(i) in item.keys():
                            i += 1
                        item['comment' + str(i)] = handle_multiline_string(strip_quotes(comment))
                        last_comment_nr = i
                else:
                    #self.logger.info("comment: '{}'".format(comment))
                    item['comment'] = handle_multiline_string(strip_quotes(comment))
                    last_comment_nr = 0
                lastline_was_comment = True
        if line is '':
            continue

        if line[0] == '[':  # item
            lastline_was_comment = False
            #
            comment_in_line = line.find('#')
            comment = line.partition('#')[2].strip()
            if comment_in_line > -1 and comment == '':
                comment = '>**<'
            line = line.partition('#')[0].strip()
            #
            brackets = 0
            level = 0
            closing = False
            for index in range(len(line)):
                if line[index] == '[' and not closing:
                    brackets += 1
                    level += 1
                elif line[index] == ']':
                    closing = True
                    brackets -= 1
                else:
                    closing = True
                    if line[index] not in valid_chars + "'":
                        #ERROR invalid characters
                        return config
            if brackets != 0:
                #"ERROR: Problem parsing '{}' unbalanced brackets in line {}: {}".format(filename, linenu, line))
                return config
            if comment_in_line > -1:
                #"ERROR: Problem parsing '{}' \nunhandled comment {} in \nline {}: {}. \nValid chars: {}".format(
                pass
            name = line.strip("[]")
            name = strip_quotes(name)
            if level == 1:
                if name not in config:
                    config[name] = collections.OrderedDict()
                item = config[name]
                parents = collections.OrderedDict()
                parents[level] = item
            else:
                if level - 1 not in parents:
                    #"ERROR: Problem parsing '{}' no parent item defined for item in line {}: {}"
                    pass
                parent = parents[level - 1]
                if name not in parent:
                    parent[name] = collections.OrderedDict()
                item = parent[name]
                parents[level] = item

        else:  # attribute
            lastline_was_comment = False
            attr, __, value = line.partition('=')
            if not value:
                continue
            attr = attr.strip()
            if not set(attr).issubset(valid_set):
                continue
            if '|' in value:
                item[attr] = [strip_quotes(x) for x in value.split('|')]
            else:
                svalue = handle_multiline_string(strip_quotes(value))
                try:
                    ivalue = int(svalue)
                    item[attr] = ivalue
                except:
                    item[attr] = svalue.replace('\t', ' ')
    return config


def convert_yaml(data):
    yaml_version = '1.1'
    indent_spaces = 4
    ordered = (type(data).__name__ == 'OrderedDict')
    dict_type = 'dict'
    if ordered:
        dict_type = 'OrderedDict'
        sdata = _ordered_dump(data, Dumper=yaml.SafeDumper, indent=indent_spaces, width=12288, allow_unicode=True,
                              default_flow_style=False)
    else:
        sdata = yaml.dump(data, Dumper=yaml.SafeDumper, indent=indent_spaces, width=12288, allow_unicode=True,
                          default_flow_style=False)
    sdata = _format_yaml_dump(sdata)

    return sdata

def _ordered_dump(data, stream=None, Dumper=yaml.Dumper, **kwds):
    """
    Ordered yaml dumper
    Use this instead ot yaml.Dumper/yaml.SaveDumper to get an Ordereddict

    :param stream: stream to write to
    :param Dumper: yaml-dumper to use
    :**kwds: Additional keywords

    :return: OrderedDict structure
    """

    # usage example: ordered_dump(data, Dumper=yaml.SafeDumper)
    class OrderedDumper(Dumper):
        pass

    def _dict_representer(dumper, data):
        return dumper.represent_mapping(
            yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
            data.items())

    OrderedDumper.add_representer(OrderedDict, _dict_representer)
    return yaml.dump(data, stream, OrderedDumper, **kwds)


def _format_yaml_dump(data):
    """
    ***Converter Special ***

    Format yaml-dump to make file more readable
    (yaml structure must be dumped to a stream before using this function)
    | Currently does the following:
    | - Add an empty line before a new item

    :param data: string to format

    :return: formatted string
    """

    data = data.replace('\n\n', '\n')
    ldata = data.split('\n')
    rdata = []

    for index, line in enumerate(ldata):
        if len(line) > 0:
            # Handle inline-comments from converter
            if line.find('##') > -1 and line.find(": '") > -1 and line[-1:] == "'":
                line = line.replace('##', '#')
                line = line.replace(": '", ": ")
                line = line[:-1]

            # Handle comments from converter
            if line.find('comment') > -1 and line.find(':') > line.find('comment'):
                #                print('comment-line>', line, '<')
                indent = len(line) - len(line.lstrip(' '))
                if ldata[index + 1][-1:] == ':':
                    indent = len(ldata[index + 1]) - len(ldata[index + 1].lstrip(' '))
                if line.find(': "|') > -1:
                    line = line[:-1]
                    line = line.replace(': "|', ': |')
                else:
                    line = line.replace(': ', ': |\\n', 1)
                # print('# ' + line[line.find("|\\n")+3:])
                line = " " * indent + '# ' + line[line.find("|\\n") + 3:]
                line = line.replace('>**<', '')
                line = line.replace('\\n', '\n' + " " * indent + '# ')

            # Handle newlines for multiline string-attributes ruamel.yaml
            if line.find(': "|') > -1 and line[-1:] == '"' and line.find('\\n') > -1:
                indent = len(line) - len(line.lstrip(' ')) + indent_spaces
                line = line[:-1]
                line = line.replace(': "|', ': |')
                line = line.replace('\\n', '\n' + " " * indent)

        rdata.append(line)

    ldata = rdata
    rdata = []
    for index, line in enumerate(ldata):
        if len(line.lstrip()) > 0 and line.lstrip()[0] == '#' and ldata[index + 1][-1:] == ':':
            rdata.append('')
            rdata.append(line)

        # Insert empty line before section (key w/o a value)
        elif line[-1:] == ':':
            if not (len(ldata[index - 1].lstrip()) > 0 and ldata[index - 1].lstrip()[0] == '#'):
                # no empty line before list attributes
                if ldata[index + 1].strip()[0] != '-':
                    rdata.append('')
                rdata.append(line)
            else:
                rdata.append(line)
        else:
            rdata.append(line)

    fdata = '\n'.join(rdata)
    if fdata[0] == '\n':
        fdata = fdata[1:]
    return fdata