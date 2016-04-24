#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2016- Martin Sinn                              m.sinn@gmx.de
#########################################################################
#  This file is part of SmartHome.py.  
#  Visit:  https://github.com/smarthomeNG/
#          https://knx-user-forum.de/forum/supportforen/smarthome-py
#
#  SmartHome.py is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  SmartHome.py is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with SmartHome.py. If not, see <http://www.gnu.org/licenses/>.
#########################################################################

import logging
import os
import shutil

import lib.config

logger = logging.getLogger('')


def findinsertline( root_contents, searchstring ):
    # look for insert point in root.html: find and return line that contains the searchstring
    iln = ''
    for ln in root_contents:
        if ln.find( searchstring ) != -1:
            iln = ln
    if iln == '':
        logger.warning("findinsertline: No insert point for pattern {0}".format(searchstring))
    return( iln )
    

def create_htmlinclude(filename, classname, shwdgdir, root_contents, iln_html, plgdir):
    insertln = root_contents.index(iln_html) +1
    # Insert widget statements to root_contents
    if insertln != 0:
        logger.debug( "create_htmlinclude: Inserting in root.html at line {0} after '{1}'".format(insertln, iln_html) )
        twig_statement = '\t{% import "' + shwdgdir + '/' + filename + '" as ' + classname + ' %}'
        logger.warning("create_htmlinclude: From '{0}': {1}".format(plgdir, twig_statement))
        root_contents.insert(insertln, twig_statement+'\n')


def create_jsinclude(filename, classname, shwdgdir, root_contents, iln_js):
    insertln = root_contents.index(iln_js)
    # Insert widget statements to root_contents
    if insertln > -1:
        logger.debug( "create_jsinclude: Inserting in root.html at line {0} before '{1}'".format(insertln, iln_js) )
        twig_statement1 = "\t{% if isfile('widgets/sh_widgets/" + filename + "') %}"
        twig_statement2 = '\t\t<script type="text/javascript" src="widgets/sh_widgets/widget_' + classname + '.js"></script>{% endif %}'
        logger.debug('create_jsinclude: {0}'.format(twig_statement1))
        logger.debug('create_jsinclude: {0}'.format(twig_statement2))
        root_contents.insert(insertln, twig_statement2+'\n')
        root_contents.insert(insertln, twig_statement1+'\n')


def create_cssinclude(filename, classname, shwdgdir, root_contents, iln_css):
    insertln = root_contents.index(iln_css)
    # Insert widget statements to root_contents
    if insertln > -1:
        logger.debug( "create_jsinclude: Inserting in root.html at line {0} before '{1}'".format(insertln, iln_css) )
        twig_statement1 = "\t{% if isfile('widgets/sh_widgets/" + filename + "') %}"
        twig_statement2 = '\t\t<script type="text/javascript" src="widgets/sh_widgets/widget_' + classname + '.css"></script>{% endif %}'
        logger.debug('create_cssinclude: {0}'.format(twig_statement1))
        logger.debug('create_cssinclude: {0}'.format(twig_statement2))
        root_contents.insert(insertln, twig_statement2+'\n')
        root_contents.insert(insertln, twig_statement1+'\n')


def copy_widgets(smarthome, plgdir, wdgdir, destdir, shwdgdir, root_contents, iln_html, iln_js, iln_css):
    # copy widgets from the sv_widget(s) subdir of a plugin
    srcdir = smarthome.base_dir + '/' + plgdir + '/' + wdgdir
    if not os.path.isdir(srcdir):
        logger.info("copy_widgets: Could not find source directory {0} in {1}".format(wdgdir, plgdir))
        return
    logger.debug("copy_widgets: Copying widgets from plugin '{0}'".format(srcdir))

    # Open file for twig import statements (for root.html)
    for fn in os.listdir(srcdir):
        if (fn[-3:] != ".md"):
            logger.info("copy_widgets: Copying widget-file: {0}".format(fn))
            shutil.copy2( srcdir + '/' + fn, destdir )
            if (fn[0:7] == "widget_") and (fn[-5:] == ".html"):
                if iln_html != '':
                    create_htmlinclude(fn, fn[7:-5] , shwdgdir, root_contents, iln_html, plgdir)

            if (fn[0:7] == "widget_") and (fn[-3:] == ".js"):
                if iln_js != '':
                    create_jsinclude(fn, fn[7:-3] , shwdgdir, root_contents, iln_js)

            if (fn[0:7] == "widget_") and (fn[-4:] == ".css"):
                if iln_css != '':
                    create_cssinclude(fn, fn[7:-4] , shwdgdir, root_contents, iln_css)


def install_widgets(smarthome, directory):
    logger.info("install_widgets; Installing to {0}".format(directory))
    logger.info("install_widgets: Installing from {0}".format(smarthome.base_dir))
    # sh directories
    wdgdir = smarthome.base_dir + '/plugins/_sv_widgets'
    # sv directories
    shwdgdir = 'sh_widgets'
    outdir = directory + '/widgets/' + shwdgdir
    tpldir = directory + '/pages/base/tpl'
    tmpdir = directory + '/temp'
    pgbdir = directory + '/pages/base'          # pages/base directory
    
    # clear temp directory
    if not os.path.isdir(tmpdir):
        logger.warning("Could not find temp directory: {0}".format(tmpdir))
        return
    for fn in os.listdir(tmpdir):
        if len(fn) != 2:  # only delete Twig temp files
            continue
        fp = os.path.join(tmpdir, fn)
        try:
            if os.path.isdir(fp):
                shutil.rmtree(fp)
        except Exception as e:
            logger.warning("Could not delete directory {0}: {1}".format(fp, e))
            
    # create destination directory for widgets
    logger.info("install_widgets: Creating  directory for widgets")
    try:
        os.mkdir(outdir)
    except:
        pass

    if not os.path.isdir(outdir):
        logger.warning("Could not find or create directory for sh widgets: {0}".format(outdir))
        return

    # remove old dynamic widget files
    logger.info("install_widgets: Removing old dynamic widget files")
    for fn in os.listdir(outdir):
        fp = os.path.join(outdir, fn)
        try:
            if os.path.isfile(fp):
                os.unlink(fp)
        except Exception as e:
            logger.warning("Could not delete file {0}: {1}".format(fp, e))

    # make a backup copy of root.html (for full integeration)
    if not os.path.isfile( pgbdir + '/root_master.html' ):
        logger.warning( "install_widgets: Creating a copy of root.html" )
        shutil.copy2( pgbdir + '/root.html', pgbdir + '/root_master.html' )

    # read the unmodified root.html (from root_master.html)
    f_root = open(pgbdir + '/root_master.html', "r")
    root_contents = f_root.readlines()
    f_root.close()
    logger.debug( "root_contents: {0}".format(root_contents) )

    iln_html = findinsertline( root_contents, '{% import "plot.html" as plot %}' )
    iln_js = findinsertline( root_contents, "{% if isfile('pages/'~config_pages~'/visu.js') %}" )
    iln_css = findinsertline( root_contents, "{% if isfile('pages/'~config_pages~'/visu.css') %}" )
    mypluginlist = []
    # copy GLOBAL widgets from _sv_widgets
    copy_widgets( smarthome, '/plugins', '_sv_widgets', outdir, shwdgdir, root_contents, iln_html, iln_js, iln_css )
    
    # copy widgets from plugin directories
    # read plungin.conf
    _conf = lib.config.parse(smarthome._plugin_conf)
    for plugin in _conf:
#        logger.warning("install_widgets: Plugin class {0}, path {1}".format(_conf[plugin]['class_name'], _conf[plugin]['class_path']))
        plgdir = _conf[plugin]['class_path']
        if plgdir not in mypluginlist:
            # process each plugin only once
            mypluginlist.append( plgdir )
            copy_widgets( smarthome, plgdir.replace('.', '/'), 'sv_widgets', outdir, shwdgdir, root_contents, iln_html, iln_js, iln_css )
    # write root.html with additions for widgets
    f_root = open(pgbdir + '/root.html', "w")
    root_contents = "".join(root_contents)
    f_root.write(root_contents)
    logger.warning( "install_widgets: Writing root.html" )
    f_root.close()


