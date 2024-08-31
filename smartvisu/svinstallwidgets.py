# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2016-     Martin Sinn                          m.sinn@gmx.de
#  Parts Copyright 2012-2013 Marcus Popp                   marcus@popp.mx
#########################################################################
#  This file is part of SmartHomeNG.
#  https://github.com/smarthomeNG/smarthome
#
#  SmartHomeNG is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  SmartHomeNG is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with SmartHomeNG. If not, see <http://www.gnu.org/licenses/>.
#########################################################################

import os
import shutil

import lib.config

class SmartVisuInstallWidgets:

    def __init__(self, plugin_instance):
        self.logger = plugin_instance.logger
        self._sh = plugin_instance._sh
        self.plugin_instance = plugin_instance
        self.smartvisu_dir = plugin_instance.smartvisu_dir
        self.smartvisu_version = plugin_instance.smartvisu_version
        self.logger.info("Installing widgets into smartVISU v{}".format(self.smartvisu_version))

        # sv directories
        self.shwdgdir = 'sh_widgets'
        self.outdir = self.smartvisu_dir + '/widgets/' + self.shwdgdir
        self.tmpdir = self.smartvisu_dir + '/temp'
        self.pgbdir = self.smartvisu_dir + '/pages/base'          # pages/base directory
        if self.smartvisu_version >= '2.9':
            # v2.9 & v3.x
            self.outdir = os.path.join(self.smartvisu_dir, 'dropins/widgets')
            self.pgbdir = os.path.join(self.smartvisu_dir, 'dropins')
            self.icndir_ws = os.path.join(self.smartvisu_dir, 'dropins/icons/ws')
            self.icndir_sw = os.path.join(self.smartvisu_dir, 'dropins/icons/sw')
        #if self.smartvisu_version >= '3.0' and self.smartvisu_version <= '3.4':
        if self.smartvisu_version >= '3.0':
            # v3.x
            self.outdir = os.path.join(self.smartvisu_dir, 'dropins/shwidgets')

        self.logger.debug("install_widgets: Installing from '{0}' to '{1}'".format(self._sh.base_dir, self.smartvisu_dir))

        self.install_widgets(self._sh)


    def install_widgets(self, smarthome):
        if not self.remove_oldfiles():
            return

        if self.smartvisu_version == '2.7' or self.smartvisu_version == '2.8':
            # make a backup copy of root.html if it doesn't exist (for full integeration)
            if not os.path.isfile( self.pgbdir + '/root_master.html' ):
                self.logger.warning( "install_widgets: Creating a copy of root.html" )
                try:
                    shutil.copy2( self.pgbdir + '/root.html', self.pgbdir + '/root_master.html' )
                except Exception as e:
                    self.logger.error("Could not copy {} from {} to {}".format('root.html', self.pgbdir, self.pgbdir + '/root_master.html'))
                    return

            # read the unmodified root.html (from root_master.html)
            f_root = open(self.pgbdir + '/root_master.html', "r")
            root_contents = f_root.readlines()
            f_root.close()
            self.logger.debug( "root_contents: {0}".format(root_contents) )

            # find insert points in original root.html
            iln_html = self.findinsertline( root_contents, '{% import "plot.html" as plot %}' )
            iln_js = self.findinsertline( root_contents, "{% if isfile('pages/'~config_pages~'/visu.js') %}" )
            iln_css = self.findinsertline( root_contents, "{% if isfile('pages/'~config_pages~'/visu.css') %}" )

        # copy widgets from plugin directories of configured plugins
        # read plungin.conf
        _conf = lib.config.parse(smarthome._plugin_conf)
        self.logger.debug( "install_widgets: _conf = {}".format(str(_conf)) )
        mypluginlist = []
        for plugin in _conf:
            self.logger.debug("install_widgets: Plugin section '{}', class_path = '{}', plugin_name = '{}'".format(plugin, str(_conf[plugin].get('class_path', '')), str(_conf[plugin].get('plugin_name', ''))))
            plgdir = _conf[plugin].get('class_path', '')
            if plgdir == '':
                plgdir = 'plugins.' + _conf[plugin].get('plugin_name', '')
            if plgdir not in mypluginlist:
                # process each plugin only once
                mypluginlist.append( plgdir )
                if self.smartvisu_version == '2.7' or self.smartvisu_version == '2.8':
                    self.copy_widgets( plgdir.replace('.', '/'), root_contents, iln_html, iln_js, iln_css )
                else:
                    self.copy_widgets( plgdir.replace('.', '/') )

        if self.smartvisu_version == '2.7' or self.smartvisu_version == '2.8':
            # write root.html with additions for widgets
            self.logger.info( "Adding import statements to root.html" )
            f_root = open(self.pgbdir + '/root.html', "w")
            root_contents = "".join(root_contents)
            f_root.write(root_contents)
            f_root.close()


#########################################################################

    def findinsertline(self, root_contents, searchstring ):
        # look for insert point in root.html: find and return line that contains the searchstring
        iln = ''
        for ln in root_contents:
            if ln.find( searchstring ) != -1:
                iln = ln
        if iln == '':
            self.logger.warning("findinsertline: No insert point for pattern {0}".format(searchstring))
        return( iln )


    def copy_widgets(self, plgdir, root_contents='', iln_html='', iln_js='', iln_css=''):
        wdgdir = 'sv_widgets'
        # copy widgets from the sv_widget(s) subdir of a plugin
        srcdir = self._sh.base_dir + '/' + plgdir + '/' + wdgdir
        if not os.path.isdir(srcdir):
            self.logger.debug("copy_widgets: Could not find source directory {} in {}".format(wdgdir, plgdir))
            return
        self.logger.debug("copy_widgets: Copying widgets from plugin '{}'".format(srcdir))

        # Open file for twig import statements (for root.html)
        for fn in os.listdir(srcdir):
            if self.smartvisu_version >= '3.0':
                # v3.x
                # copy icons from subirectories ws and sw (if fn is one of the directories)
                if (fn in ['ws', 'sw']) and os.path.isdir(os.path.join(srcdir, fn)):
                    icondir = os.path.join(srcdir, fn)
                    for icn in os.listdir(icondir):
                        if fn == 'ws':
                            shutil.copy2(os.path.join(icondir, icn), self.icndir_ws)
                        if fn == 'sw':
                            shutil.copy2(os.path.join(icondir, icn), self.icndir_sw)

            # copy files from the widget directory (if it is not a marrkdown file)
            if (fn[-3:] != ".md"):
                self.logger.info("copy_widgets (v{}): Copying widget-file: {} from {}".format(self.smartvisu_version, fn, plgdir))
                if fn.startswith('widget_'):
                    self.plugin_instance.test_widget_for_deprecated_widgets(os.path.join(srcdir, fn))

                if self.smartvisu_version >= '2.9':
                    # v2.9 & v3.x
                    if os.path.splitext(fn)[1] == '.png' or os.path.splitext(fn)[1] == '.svg':
                        # copy icons to the icons directory
                        shutil.copy2( os.path.join(srcdir, fn), self.icndir_ws )
                    else:
                        # the rest to the widgets directory & strip 'widgets_' from name
                        if fn.startswith('widget_'):
                            dn = fn[len('widget_'):]
                            shutil.copy2( os.path.join(srcdir, fn), os.path.join(self.outdir, dn) )
                        else:
                            shutil.copy2( os.path.join(srcdir, fn), self.outdir )

                else:
                    # v2.7 & v2.8
                    shutil.copy2( srcdir + '/' + fn, self.outdir )

                if self.smartvisu_version == '2.7' or self.smartvisu_version == '2.8':
                    if (fn[0:7] == "widget_") and (fn[-5:] == ".html"):
                        self.logger.info("- Installing for SV v{} from '{}': {}".format(self.smartvisu_version, plgdir, '\t' + fn))
                        if iln_html != '':
                            self.create_htmlinclude(fn, fn[7:-5] , root_contents, iln_html)
                    if (fn[0:7] == "widget_") and (fn[-3:] == ".js"):
                        if iln_js != '':
                            self.create_jsinclude(fn, fn[7:-3] , root_contents, iln_js)
                    if (fn[0:7] == "widget_") and (fn[-4:] == ".css"):
                        if iln_css != '':
                            self.create_cssinclude(fn, fn[7:-4] , root_contents, iln_css)
        return


    def create_htmlinclude(self, filename, classname, root_contents, iln_html):
        insertln = root_contents.index(iln_html) +1
        # Insert widget statements to root_contents
        if insertln != 0:
            self.logger.debug( "create_htmlinclude: Inserting in root.html at line {0} after '{1}'".format(insertln, iln_html) )
            twig_statement = '\t{% import "' + self.shwdgdir + '/' + filename + '" as ' + classname + ' %}'
            root_contents.insert(insertln, twig_statement+'\n')


    def create_jsinclude(self, filename, classname, root_contents, iln_js):
        insertln = root_contents.index(iln_js)
        # Insert widget statements to root_contents
        if insertln > -1:
            self.logger.debug( "create_jsinclude: Inserting in root.html at line {0} before '{1}'".format(insertln, iln_js) )
            twig_statement1 = "\t{% if isfile('widgets/sh_widgets/" + filename + "') %}"
            twig_statement2 = '\t\t<script type="text/javascript" src="widgets/sh_widgets/widget_' + classname + '.js"></script>{% endif %}'
            self.logger.debug('create_jsinclude: {0}'.format(twig_statement1))
            self.logger.debug('create_jsinclude: {0}'.format(twig_statement2))
            root_contents.insert(insertln, twig_statement2+'\n')
            root_contents.insert(insertln, twig_statement1+'\n')


    def create_cssinclude(self, filename, classname, root_contents, iln_css):
        insertln = root_contents.index(iln_css)
        # Insert widget statements to root_contents
        if insertln > -1:
            self.logger.debug( "create_jsinclude: Inserting in root.html at line {0} before '{1}'".format(insertln, iln_css) )
            twig_statement1 = "\t{% if isfile('widgets/sh_widgets/" + filename + "') %}"
            twig_statement2 = '\t\t<link rel="stylesheet" type="text/css" href="widgets/sh_widgets/widget_' + classname + '.css" />{% endif %}'
            self.logger.debug('create_cssinclude: {0}'.format(twig_statement1))
            self.logger.debug('create_cssinclude: {0}'.format(twig_statement2))
            root_contents.insert(insertln, twig_statement2+'\n')
            root_contents.insert(insertln, twig_statement1+'\n')


    def remove_oldfiles(self):
        # clear temp directory
        if not os.path.isdir(self.tmpdir):
            self.logger.warning("Could not find temp directory: {0}".format(self.tmpdir))
            return False
        for fn in os.listdir(self.tmpdir):
            if len(fn) != 2:  # only delete Twig temp files
                continue
            fp = os.path.join(self.tmpdir, fn)
            try:
                if os.path.isdir(fp):
                    shutil.rmtree(fp)
            except Exception as e:
                self.logger.warning("Could not delete directory {0}: {1}".format(fp, e))

        # create destination directory for widgets
        self.logger.debug("install_widgets: Creating directory for widgets")
        try:
            os.mkdir(self.outdir)
        except:
            pass

        if not os.path.isdir(self.outdir):
            self.logger.warning("Could not find or create directory for sh widgets: {0}".format(self.outdir))
            return False

        # remove old dynamic widget files
        self.logger.debug("install_widgets: Removing old dynamic widget files")
        for fn in os.listdir(self.outdir):
            fp = os.path.join(self.outdir, fn)
            try:
                if os.path.isfile(fp):
                    os.unlink(fp)
            except Exception as e:
                self.logger.warning("Could not delete file {0}: {1}".format(fp, e))

        return True

