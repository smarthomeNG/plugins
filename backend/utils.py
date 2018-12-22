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


logger = logging.getLogger(__name__)


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
        logger.error("load_translation language='{0}' failed: Error '{1}'".format('en', e))
    logger.debug("translation_dict_en='{0}'".format(translation_dict_en))

    lang_filename = os.path.dirname(os.path.abspath(__file__)) + '/locale/' + 'de' + '.json'
    try:
        f = open(lang_filename, 'r')
        translation_dict_de = json.load(f)
    except Exception as e:
        translation_dict_de = {}
        logger.error("load_translation language='{0}' failed: Error '{1}'".format('de', e))
    logger.debug("translation_dict_de='{0}'".format(translation_dict_de))

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
            logger.error("load_translation language='{0}' failed: Error '{1}'".format(translation_lang, e))
            return False
        try:
            translation_dict = json.load(f)
        except Exception as e:
            logger.error("load_translation language='{0}': Error '{1}'".format(translation_lang, e))
            return False
    logger.debug("translation_dict='{0}'".format(translation_dict))
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
            logger.info("Language '{0}': Translation for '{1}' is missing!".format(translation_lang, txt))
            tr = _get_translation_for_block('en', txt, block)
            if tr == '':
                tr = _get_translation_for_block('de', txt, block)
    else:
        tr = translation_dict.get(txt, '')
        if tr == '':
            logger.info("Language '{0}': Translation for '{1}' is missing".format(translation_lang, txt))
            tr = translation_dict_en.get(txt, '')
            if tr == '':
                logger.info("Language '{0}': Translation for '{1}' is missing".format('en', txt))
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
            logger.info("translate: -> Language '{0}': Translation for '{1}' is missing".format(translation_lang, txt))
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


def get_process_info(command, wait=True):
    """
    returns output from executing a given command via the shell.
    """
    ## get subprocess module
    import subprocess

    ## call date command ##
    p = subprocess.Popen(command, stdout=subprocess.PIPE, shell=True)

    # Talk with date command i.e. read data from stdout and stderr. Store this info in tuple ##
    # Interact with process: Send data to stdin. Read data from stdout and stderr, until end-of-file is reached.
    # Wait for process to terminate. The optional input argument should be a string to be sent to the child process, or None, if no data should be sent to the child.
    (result, err) = p.communicate()
#    logger.warning("get_process_info: command='{}', result='{}', err='{}'".format(command, result, err))

    if wait:
        ## Wait for date to terminate. Get return returncode ##
        p_status = p.wait()
    return str(result, encoding='utf-8', errors='strict')3rdpartylicenses.txt
assets
color.c7a33805ffda0d32bd2a.png
fa-brands-400.3f4d4ad447e748754e99.svg
fa-brands-400.a31c967484b343189fc5.eot
fa-brands-400.dec02372212aab5a2e52.ttf
fa-brands-400.e4a6cecbe2bb89b0722b.woff2
fa-brands-400.eef6051639f95300dbf0.woff
fa-regular-400.0e2e26fb3527ae47f9eb.ttf
fa-regular-400.52899632324b722c9c79.woff
fa-regular-400.b5a61b229c9c92a6ac21.svg
fa-regular-400.c38ef825039cbe8ec76d.eot
fa-regular-400.dd25437adf06f377113f.woff2
fa-solid-900.3f759796d3d16b843484.svg
fa-solid-900.09bc9e8c7d6dfdace635.woff
fa-solid-900.baa1e2496e8c71f63658.eot
fa-solid-900.e143b57de78138e6d596.ttf
fa-solid-900.fd531d212b567d6049f4.woff2
favicon.ico
hue.0614c27197fc3ce572e1.png
index.html
line.567f57385ea3dde2c9ae.gif
loading.8732a6660b528fadfaeb.gif
main.b7498a334d5bb97ef8e4.js
password-meter.d59e6dc2616c53ce8e77.png
polyfills.d1c7bf4a2ae7c3435f95.js
primeicons.38d77552b0353684a208.svg
primeicons.71bb3d79dcf18b45ae84.woff
primeicons.473e2a746d3c151d7dca.ttf
primeicons.b8eccb1059ea5faaf6d8.eot
roboto-v15-latin-regular.3d3a53586bd78d1069ae.svg
roboto-v15-latin-regular.7e367be02cd17a96d513.woff2
roboto-v15-latin-regular.9f916e330c478bbfa2a0.eot
roboto-v15-latin-regular.16e1d930cf13fb7a9563.woff
roboto-v15-latin-regular.38861cba61c66739c145.ttf
runtime.ec2944dd8b20ec099bf3.js
scripts.bf34f41efa4f4868edea.js
slider_handles.1868e2550c9853a938a6.png
styles.b129e6ddb26879580c4a.css3rdpartylicenses.txt
color.c7a33805ffda0d32bd2a.png
fa-brands-400.3f4d4ad447e748754e99.svg
fa-brands-400.a31c967484b343189fc5.eot
fa-brands-400.dec02372212aab5a2e52.ttf
fa-brands-400.e4a6cecbe2bb89b0722b.woff2
fa-brands-400.eef6051639f95300dbf0.woff
fa-regular-400.0e2e26fb3527ae47f9eb.ttf
fa-regular-400.52899632324b722c9c79.woff
fa-regular-400.b5a61b229c9c92a6ac21.svg
fa-regular-400.c38ef825039cbe8ec76d.eot
fa-regular-400.dd25437adf06f377113f.woff2
fa-solid-900.3f759796d3d16b843484.svg
fa-solid-900.09bc9e8c7d6dfdace635.woff
fa-solid-900.baa1e2496e8c71f63658.eot
fa-solid-900.e143b57de78138e6d596.ttf
fa-solid-900.fd531d212b567d6049f4.woff2
favicon.ico
hue.0614c27197fc3ce572e1.png
index.html
line.567f57385ea3dde2c9ae.gif
loading.8732a6660b528fadfaeb.gif
main.8aa979b98626a369d1e4.js
password-meter.d59e6dc2616c53ce8e77.png
polyfills.d1c7bf4a2ae7c3435f95.js
primeicons.38d77552b0353684a208.svg
primeicons.71bb3d79dcf18b45ae84.woff
primeicons.473e2a746d3c151d7dca.ttf
primeicons.b8eccb1059ea5faaf6d8.eot
roboto-v15-latin-regular.3d3a53586bd78d1069ae.svg
roboto-v15-latin-regular.7e367be02cd17a96d513.woff2
roboto-v15-latin-regular.9f916e330c478bbfa2a0.eot
roboto-v15-latin-regular.16e1d930cf13fb7a9563.woff
roboto-v15-latin-regular.38861cba61c66739c145.ttf
runtime.ec2944dd8b20ec099bf3.js
scripts.bf34f41efa4f4868edea.js
slider_handles.1868e2550c9853a938a6.png
styles.b129e6ddb26879580c4a.css


def os_with_systemd():
    """
    Returns True, if running systemd on the computer

    :return:
    """
    result = get_process_info("systemctl --version")
    return (result != '')


def os_with_sysvinit():
    """
    Returns True, if running SysVinit on the computer

    :return:
    """
    return os.path.isfile('/usr/sbin/service')


def os_service_controllable():
    """
    Test if services are contollable by backend

    :return: True, if service is controllable
    """
    return (os_with_systemd() or os_with_sysvinit())


def os_service_status(servicename):
    """
    Returns if the specified service is active (running)

    :param servicename: str
    :return: bool
    """
    result_b = False
    if os_with_systemd():
        result = get_process_info("systemctl status {}".format(servicename))
        if result.find('Active: inactive') != -1:
            result_b = False
        elif result.find('Active: active') != -1:
            result_b = True
        else:
            logger.warning("os_service_status (systemd): Cannot determine status of service (result='{}')".format(result))
    elif os_with_sysvinit():
        result = get_process_info("/usr/sbin/service {} status".format(servicename))
        if result.find('FAIL') != -1:
            result_b = False
        elif result.find(' ok ') != -1:
            result_b = True
        else:
            logger.warning("os_service_status (SysVInit): Cannot determine status of service (result='{}')".format(result))
    else:
        result = "os_service_status: Cannot determine status of service"
        result_b = False
        logger.warning("os_service_status: Cannot determine status of service")
#    logger.warning("os_service_status: result = '{}' -> {}".format(result, result_b))
    return result_b

def os_service_restart(servicename):
    """
    Restart a service

    :param servicename:
    :return:
    """
    logger.warning("os_service_restart: Restarting SmartHomeNG")
    if os_with_systemd():
            result = get_process_info("sudo systemctl restart {}.service".format(servicename), wait=False)
    elif os_with_sysvinit():
        result = get_process_info("sudo service {} restart".format(servicename), wait=False)
    else:
        logger.warning("os_service_restart: Cannot restart service")


def os_restart_shng(pid):
    """
    Restart a service

    :param pid:
    """
    result = get_process_info("ps -f -p {}".format(pid))
    cmdpos = result.find('CMD')
    result = result[result.find('\n')+1:]
    cmd = result[cmdpos:]
    cmd = cmd[:cmd.find('.py')+3]
    logger.warning("os_service_shng: ps -f -p {} -> '{}'".format(pid, cmd))

    logger.warning("os_service_shng: 1. Restart -> '{} -r'".format(cmd))
    result = get_process_info("{} -r".format(cmd), wait=False)
    logger.warning("os_service_shng: 2. Restart -> '{} -r'".format(cmd))


# PIDFILE in smarthome.py als global definiert
# self.get_sh()._pidfile
# lib.daemon.read_pidfile(PIDFILE)
#
# lib.daemon.read_pidfile(self.get_sh()._pidfile)
#
# > ps -f -p 14266
# UID        PID  PPID  C STIME TTY          TIME CMD
# smartho+ 14266     1  3 Mai17 ?        00:50:30 python bin/smarthome.py -r
#
