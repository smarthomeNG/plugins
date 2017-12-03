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
import html
import collections
from collections import OrderedDict

from lib.logic import Logics


translation_dict = {}
translation_dict_en = {}
translation_dict_de = {}
translation_lang = ''


def get_translation_lang():
    global translation_lang
    return translation_lang


def load_translation_backuplanguages():
    global translation_dict_en  # Needed to modify global copy of translation_dict
    global translation_dict_de  # Needed to modify global copy of translation_dict

    logger = logging.getLogger(__name__)

    lang_filename = os.path.dirname(os.path.abspath(__file__)) + '/locale/' + 'en' + '.json'
    try:
        f = open(lang_filename, 'r')
        translation_dict_en = json.load(f)
    except Exception as e:
        translation_dict_en = {}
        logger.error("Backend: load_translation language='{0}' failed: Error '{1}'".format('en', e))
    logger.debug("Backend: translation_dict_en='{0}'".format(translation_dict_en))

    lang_filename = os.path.dirname(os.path.abspath(__file__)) + '/locale/' + 'de' + '.json'
    try:
        f = open(lang_filename, 'r')
        translation_dict_de = json.load(f)
    except Exception as e:
        translation_dict_de = {}
        logger.error("Backend: load_translation language='{0}' failed: Error '{1}'".format('de', e))
    logger.debug("Backend: translation_dict_de='{0}'".format(translation_dict_de))

    return


def load_translation(language):
    global translation_dict  # Needed to modify global copy of translation_dict
    global translation_lang  # Needed to modify global copy of translation_lang

    logger = logging.getLogger(__name__)

    if translation_dict_en == {}:
        load_translation_backuplanguages()

    translation_lang = language.lower()
    if translation_lang == '':
        translation_dict = {}
    else:
        lang_filename = os.path.dirname(os.path.abspath(__file__)) + '/locale/' + translation_lang + '.json'
        try:
            f = open(lang_filename, 'r')
        except Exception as e:
            translation_lang = ''
            logger.error("Backend: load_translation language='{0}' failed: Error '{1}'".format(translation_lang, e))
            return False
        try:
            translation_dict = json.load(f)
        except Exception as e:
            logger.error("Backend: load_translation language='{0}': Error '{1}'".format(translation_lang, e))
            return False
    logger.debug("Backend: translation_dict='{0}'".format(translation_dict))
    return True


def _get_translation_for_block(lang, txt, block):
    """
    """
    if lang == 'en':
        blockdict = translation_dict_en.get('_' + block, {})
    elif lang == 'de':
        blockdict = translation_dict_de.get('_' + block, {})
    else:
        blockdict = translation_dict.get('_' + block, {})

    return blockdict.get(txt, '')
        
        
def _get_translation(txt, block):
    """
    Get translation with fallback to english and further fallback to german
    """
    logger = logging.getLogger(__name__)

    if block != '':
        tr = _get_translation_for_block('', txt, block)
        if tr == '':
            logger.info("Backend: Language '{0}': Translation for '{1}' is missing!".format(translation_lang, txt))
            tr = _get_translation_for_block('en', txt, block)
            if tr == '':
                tr = _get_translation_for_block('de', txt, block)
    else:
        tr = translation_dict.get(txt, '')
        if tr == '':
            logger.info("Backend: Language '{0}': Translation for '{1}' is missing".format(translation_lang, txt))
            tr = translation_dict_en.get(txt, '')
            if tr == '':
                logger.info("Backend: Language '{0}': Translation for '{1}' is missing".format('en', txt))
                tr = translation_dict_de.get(txt, '')
    return tr
    

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
        tr = _get_translation(txt, block)

        if tr == '':
            logger.info("Backend: -> Language '{0}': Translation for '{1}' is missing".format(translation_lang, txt))
            tr = txt
    return html.escape(tr)


def create_hash(plaintext):
    import hashlib
    hashfunc = hashlib.sha512()
    hashfunc.update(plaintext.encode())
    return hashfunc.hexdigest()


def parse_requirements(file_path):
    req_dict = {}
    try:
        fobj = open(file_path)
    except:
        return req_dict

    for rline in fobj:
        line = ''
        if len(rline) > 0:
            if rline.find('#') == -1:
                line = rline.lower().strip()
            else:
                line = line[0:line.find("#")].lower().strip()
            
        if len(line) > 0:
            if ">" in line:
                if line[0:line.find(">")].lower().strip() in req_dict:
                    req_dict[line[0:line.find(">")].lower().strip()] += " | " + line[line.find(">"):len(
                        line)].lower().strip()
                else:
                    req_dict[line[0:line.find(">")].lower().strip()] = line[line.find(">"):len(line)].lower().strip()
            elif "<" in line:
                if line[0:line.find("<")].lower().strip() in req_dict:
                    req_dict[line[0:line.find("<")].lower().strip()] += " | " + line[line.find("<"):len(
                        line)].lower().strip()
                else:
                    req_dict[line[0:line.find("<")].lower().strip()] = line[line.find("<"):len(line)].lower().strip()
            elif "=" in line:
                if line[0:line.find("=")].lower().strip() in req_dict:
                    req_dict[line[0:line.find("=")].lower().strip()] += " | " + line[line.find("="):len(
                        line)].lower().strip()
                else:
                    req_dict[line[0:line.find("=")].lower().strip()] = line[line.find("="):len(line)].lower().strip()
            else:
                req_dict[line.lower().strip()] = '==*'

    fobj.close()
    return req_dict

