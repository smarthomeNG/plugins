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
    pgbdir = directory + '/pages/base'			# pages/base directory
    
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
    
    # look for insert point
    searchstring = '{% import "plot.html" as plot %}'
    iln = 'xyz'
    for ln in root_contents:
        if ln.find( searchstring ) != -1:
            iln = ln
    try:
        insertln = root_contents.index(iln) +1
    except:
        insertln = 0

    # copy GLOBAL widgets from _sv_widgets
    copy_widgets( smarthome.base_dir + '/plugins', '_sv_widgets', outdir, shwdgdir, root_contents, insertln )
    
    # copy widgets from plugin directories
    # read plunginn.conf
    _conf = lib.config.parse(smarthome._plugin_conf)
    for plugin in _conf:
#        logger.warning("install_widgets: Plugin class {0}, path {1}".format(_conf[plugin]['class_name'], _conf[plugin]['class_path']))
        plgdir = _conf[plugin]['class_path']
        copy_widgets( smarthome.base_dir + '/' + plgdir.replace('.', '/'), 'sv_widgets', outdir, shwdgdir, root_contents, insertln )

    # Insert widget statements to root_contents
    if insertln != 0:
        logger.warning( "install_widgets: Inserting in root.html at line {0} after '{1}'".format(insertln, searchstring) )
    else:
        logger.error( "install_widgets: Cannot find insert point in root.html (file=root_master.html)" )
    
	# write root.html with additions for widgets
    f_root = open(pgbdir + '/root.html', "w")
    root_contents = "".join(root_contents)
    f_root.write(root_contents)
    f_root.close()


def copy_widgets(plgdir, wdgdir, destdir, shwdgdir, root_contents, insertln):
    # copy widgets from _sv_widgets
    srcdir = plgdir + '/' + wdgdir
    if not os.path.isdir(srcdir):
        logger.info("copy_widgets: Could not find source directory {0} in {1}".format(wdgdir, plgdir))
        return
    logger.warning("copy_widgets: Copying widgets from plugin '{0}'".format(srcdir))

    # Open file for twig import statements (for root.html)
    fh = open(destdir + "/_sh_widgets.html", "w")
    for fn in os.listdir(srcdir):
        logger.info("copy_widgets: Copying widget-file: {0}".format(fn))
        shutil.copy2( srcdir + '/' + fn, destdir )
        if (fn[0:7] == "widget_") and (fn[-5:] == ".html"):
            create_widget_twig(fn, fn[7:-5] , fh, shwdgdir, root_contents, insertln)
    fh.close()


def create_widget_twig(filename, classname, twig_fh, shwdgdir, root_contents, insertln):
    twig_statement = '\t{% import "' + shwdgdir + '/' + filename + '" as ' + classname + ' %}'
    logger.warning('create_widget_twig: {0}'.format(twig_statement))
    
    twig_fh.write(twig_statement+'\n')
    if insertln > 0:
        root_contents.insert(insertln, twig_statement+'\n')
