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

from lib.item import Items

class SmartVisuGenerator:

    def __init__(self, plugin_instance):
        self.logger = plugin_instance.logger
        self._sh = plugin_instance._sh
        self.items = Items.get_instance()
        self.plugin_instance = plugin_instance

        self.smartvisu_dir = plugin_instance.smartvisu_dir
        self.smartvisu_version = plugin_instance.smartvisu_version
        self.overwrite_templates = plugin_instance.overwrite_templates
        self.visu_style = plugin_instance.visu_style.lower()
        if not self.visu_style in ['std','blk']:
            self.visu_style = 'std'
            self.logger.warning("SmartVisuGenerator: visu_style '{}' unknown, using visu_style '{1}'".format(plugin_instance.visu_style, self.visu_style))
        self.list_deprecated_warnings = plugin_instance.list_deprecated_warnings

        self.logger.info("Generating pages for smartVISU v{}".format(self.smartvisu_version))

        self.thisplg_dir = os.path.dirname(os.path.abspath(__file__))
        self.shng_tpldir = os.path.join(self.thisplg_dir, 'tplNG')

        self.sv_tpldir = os.path.join(self.smartvisu_dir, 'pages', '_template')
        self.gen_tpldir = os.path.join(self.smartvisu_dir, 'pages', 'base', 'tplNG')
        if self.smartvisu_version >= '2.9':
            self.gen_tpldir = os.path.join(self.smartvisu_dir, 'dropins')

        self.tmpdir = os.path.join(self.smartvisu_dir, 'temp')
        self.pages_dir = os.path.join(self.smartvisu_dir, 'pages', 'smarthome')

        self.copy_templates()

        self.pages()
        self.logger.info("Generating pages for smartVISU v{} End".format(self.smartvisu_version))


    def handle_heading_attributes(self, room):
        if 'sv_heading_right' in room.conf:
            heading_right = room.conf['sv_heading_right']
        else:
            heading_right = ''
        if 'sv_heading_center' in room.conf:
            heading_center = room.conf['sv_heading_center']
        else:
            heading_center = ''
        if 'sv_heading_left' in room.conf:
            heading_left = room.conf['sv_heading_left']
        else:
            heading_left = ''
        if heading_right != '' or heading_center != '' or heading_left != '':
            heading = self.parse_tpl('heading.html', [('{{ visu_heading_right }}', heading_right), ('{{ visu_heading_center }}', heading_center), ('{{ visu_heading_left }}', heading_left)])
        else:
            heading = ''
        return heading


    def get_widgetblocksize(self, item):
        """
        Returns the blocksize for the block in which the item is to be displayed.

        :param item: Item to be displayed

        :return: The set number ('1'..'3') as defined in smartVISUs css
        :rytpe: str
        """
        if 'sv_blocksize' in item.conf:
            blocksize = item.conf['sv_blocksize']
            if not blocksize in ['1','2','3']:
                blocksize = '2'
        else:
            blocksize = '2'
        return blocksize


    def get_attribute(self, attr, item):
        if attr in item.conf:
            attrvalue = item.conf[attr]
        else:
            attrvalue = ''
        return attrvalue


    def room(self, room):
        """
        Interpretation of the room-specific item-attributes.
        This routine is called once per 'sv_page'.

        :param room: Items (with room configuration)

        :return: html code to be included in the visu file for the room
        :rtype: str
        """
        block_style = 'std' # 'std' or 'noh'
        widgetblocktemplate = 'widgetblock_' + self.visu_style + '_' + block_style + '.html'
        widgetblocktemplate2 = 'widgetblock2_' + self.visu_style + '_' + block_style + '.html'
        widgets = ''

        rimg = self.get_attribute('sv_img', room)
        heading = self.handle_heading_attributes(room)

        if 'sv_widget' in room.conf:
            items = [room]
        else:
            items = []

        if (room.conf['sv_page'] == 'room') or (room.conf['sv_page'] == 'room_lite'):
#            items.extend(self._sh.find_children(room, 'sv_widget'))
            items.extend(self.items.find_children(room, 'sv_widget'))
        elif room.conf['sv_page'] == 'category':
#            items.extend(self._sh.find_children(room, 'sv_widget'))
            items.extend(self.items.find_children(room, 'sv_widget'))
        elif room.conf['sv_page'] == 'overview':
#            items.extend(self._sh.find_items('sv_item_type'))
            items.extend(self.items.find_items('sv_item_type'))

        r = ''
        for item in items:
            if room.conf['sv_page'] == 'overview' and not item.conf['sv_item_type'] == room.conf['sv_overview']:
                continue
            if 'sv_img' in item.conf:
                img = item.conf['sv_img']
            else:
                img = ''

            self.plugin_instance.test_item_for_deprecated_widgets(item)

            if isinstance(item.conf['sv_widget'], list):
                self.logger.warning("room: sv_widget: IsList")
                for widget in item.conf['sv_widget']:
                    widgets += self.parse_tpl(widgetblocktemplate, [('{{ visu_name }}', str(item)), ('{{ visu_img }}', img), ('{{ visu_widget }}', widget), ('item.name', str(item)), ("'item", "'" + item.id())])
            else:
                widget = self.get_attribute('sv_widget', item)
                name1 = self.get_attribute('sv_name1', item)
                if name1 == '':
                    name1 = item

                blocksize = self.get_widgetblocksize(item)

                widget2 = self.get_attribute('sv_widget2', item)
                if widget2 == '':
                    widgets += self.parse_tpl(widgetblocktemplate, [('{{ visu_name }}', str(name1)), ('{{ blocksize }}', str(blocksize)), ('{{ visu_img }}', img), ('{{ visu_widget }}', widget), ('item.name', str(item)), ("'item", "'" + item.id())])
                else:
                    name2 = self.get_attribute('sv_name2', item)
                    widgets += self.parse_tpl(widgetblocktemplate2, [('{{ visu_name }}', str(name1)), ('{{ visu_name2 }}', str(name2)), ('{{ visu_img }}', img), ('{{ visu_widget }}', widget), ('{{ visu_widget2 }}', widget2), ('item.name', str(item)), ("'item", "'" + item.id())])

            if room.conf['sv_page'] == 'room':
                r = self.parse_tpl('room.html', [('{{ visu_name }}', str(room)), ('{{ visu_widgets }}', widgets), ('{{ visu_img }}', rimg), ('{{ visu_heading }}', heading)])
            elif room.conf['sv_page'] == 'overview':
                r = self.parse_tpl('room.html', [('{{ visu_name }}', str(room)), ('{{ visu_widgets }}', widgets), ('{{ visu_img }}', rimg), ('{{ visu_heading }}', heading)])
            elif room.conf['sv_page'] == 'category':
                r = self.parse_tpl('category_page.html', [('{{ visu_name }}', str(room)), ('{{ visu_widgets }}', widgets), ('{{ visu_img }}', rimg), ('{{ visu_heading }}', heading)])
            elif room.conf['sv_page'] == 'room_lite':
                r = self.parse_tpl('roomlite.html', [('{{ visu_name }}', str(room)), ('{{ visu_widgets }}', widgets), ('{{ visu_img }}', rimg), ('{{ visu_heading }}', heading)])
        return r


    def pages(self):
        if not self.remove_oldpages():
            return

        nav_lis = ''
        cat_lis = ''
        lite_lis = ''

        for item in self.items.find_items('sv_page'):
            if item.conf['sv_page'] in ['separator', 'seperator']:
                nav_lis += self.parse_tpl('navi_sep.html', [('{{ name }}', str(item))])
                continue
            elif item.conf['sv_page'] in ['cat_separator', 'cat_seperator']:
                cat_lis += self.parse_tpl('navi_sep.html', [('{{ name }}', str(item))])
                continue
            elif ((item.conf['sv_page'] == 'overview') or (item.conf['sv_page'] == 'cat_overview')) and (not 'sv_overview' in item.conf):
                self.logger.error("missing sv_overview for {0}".format(item.id()))
                continue

            r = self.room(item)

            img = self.get_attribute('sv_img', item)

            self.plugin_instance.test_item_for_deprecated_widgets(item)

            if 'sv_nav_aside' in item.conf:
                if isinstance(item.conf['sv_nav_aside'], list):
                    nav_aside = ', '.join(item.conf['sv_nav_aside'])
                else:
                    nav_aside = item.conf['sv_nav_aside']
            else:
                nav_aside = ''
            if 'sv_nav_aside2' in item.conf:
                if isinstance(item.conf['sv_nav_aside2'], list):
                    nav_aside2 = ', '.join(item.conf['sv_nav_aside2'])
                else:
                    nav_aside2 = item.conf['sv_nav_aside2']
            else:
                nav_aside2 = ''
            if (item.conf['sv_page'] == 'category') or (item.conf['sv_page'] == 'cat_overview'):
                cat_lis += self.parse_tpl('navi.html', [('{{ visu_page }}', item.id()), ('{{ visu_name }}', str(item)), ('{{ visu_img }}', img), ('{{ visu_aside }}', nav_aside), ('{{ visu_aside2 }}', nav_aside2), ('item.name', str(item)), ("'item", "'" + item.id())])
            elif item.conf['sv_page'] == 'room':
                nav_lis += self.parse_tpl('navi.html', [('{{ visu_page }}', item.id()), ('{{ visu_name }}', str(item)), ('{{ visu_img }}', img), ('{{ visu_aside }}', nav_aside), ('{{ visu_aside2 }}', nav_aside2), ('item.name', str(item)), ("'item", "'" + item.id())])
            elif item.conf['sv_page'] == 'overview':
                nav_lis += self.parse_tpl('navi.html', [('{{ visu_page }}', item.id()), ('{{ visu_name }}', str(item)), ('{{ visu_img }}', img), ('{{ visu_aside }}', nav_aside), ('{{ visu_aside2 }}', nav_aside2), ('item.name', str(item)), ("'item", "'" + item.id())])
            elif item.conf['sv_page'] == 'room_lite':
                lite_lis += self.parse_tpl('navi.html', [('{{ visu_page }}', item.id()), ('{{ visu_name }}', str(item)), ('{{ visu_img }}', img), ('{{ visu_aside }}', nav_aside), ('{{ visu_aside2 }}', nav_aside2), ('item.name', str(item)), ("'item", "'" + item.id())])
            else:
                self.logger.warning("{}: 'sv_page' attribute contains unknown value '{}'".format(item.id(), item.conf['sv_page']))
            self.write_parseresult(item.id()+'.html', r)

        nav = self.parse_tpl('navigation.html', [('{{ visu_navis }}', nav_lis)])
        self.write_parseresult('rooms_menu.html', nav)

        nav = self.parse_tpl('navigation.html', [('{{ visu_navis }}', cat_lis)])
        self.write_parseresult('category_nav.html', nav)

        nav = self.parse_tpl('navigation.html', [('{{ visu_navis }}', lite_lis)])
        self.write_parseresult('roomlite_nav.html', nav)

        # copy templates from

        self.copy_tpl('rooms.html')
        self.copy_tpl('roomslite.html')
        self.copy_tpl('category.html')
        self.copy_tpl('index.html')


#########################################################################

    def parse_tpl(self, template, replace):
        self.logger.debug("try to parse template file '{0}'".format(template))
        try:
            with open(self.gen_tpldir + '/' + template, 'r', encoding='utf-8') as f:
                tpl = f.read()
                tpl = tpl.lstrip('\ufeff')  # remove BOM
        except Exception as e:
            self.logger.error("Could not read template file '{0}': {1}".format(template, e))
            return ''
        for s, r in replace:
            tpl = tpl.replace(s, r)
        return tpl


    def write_parseresult(self, htmlfile, parseresult):
        try:
            with open(self.pages_dir + '/' + htmlfile, 'w') as f:
                f.write(parseresult)
        except Exception as e:
            self.logger.warning("Could not write to {0}/{1}: {2}".format(self.pages_dir, htmlfile, e))


    def copy_tpl(self, tplname, destname=''):
        if destname == '':
            destname = tplname
        try:
            shutil.copy(self.gen_tpldir + '/' + tplname, self.pages_dir + '/' + destname)
        except Exception as e:
            self.logger.error("Could not copy {0} from {1} to {2}".format(tplname, self.gen_tpldir, self.destdir))


#########################################################################

    def remove_oldpages(self):
        if not os.path.isdir(self.tmpdir):
            self.logger.warning("Could not find directory: {0}".format(self.tmpdir))
            return False
        # clear temp directory
        for dn in os.listdir(self.tmpdir):
            if len(dn) != 2:  # only delete Twig temp files
                continue
            dp = os.path.join(self.tmpdir, dn)
            try:
                if os.path.isdir(dp):
                    shutil.rmtree(dp)
            except Exception as e:
                self.logger.warning("Could not delete directory {0}: {1}".format(dp, e))
        # create output directory
        try:
            os.mkdir(self.pages_dir)
        except:
            pass
        # remove old dynamic files
        if not os.path.isdir(self.pages_dir):
            self.logger.warning("Could not find/create directory: {0}".format(self.pages_dir))
            return False
        for fn in os.listdir(self.pages_dir):
            fp = os.path.join(self.pages_dir, fn)
            try:
                if os.path.isfile(fp):
                    os.unlink(fp)
            except Exception as e:
                self.logger.warning("Could not delete file {0}: {1}".format(fp, e))
        return True

#########################################################################

    def copy_templates(self):
        """
        Copy templates from this plugin to the location inside smartVISU from which they are
        used during the generation of the visu pages
        """
        self.shng_tpldir = os.path.join(self.thisplg_dir, 'tplNG')
        if not os.path.isdir(self.shng_tpldir):
            self.logger.warning("copy_templates: Could not find source directory {}".format(self.shng_tpldir))
            return

        if self.smartvisu_version >= '2.9':
            for fn in os.listdir(self.shng_tpldir):
                if (self.overwrite_templates) or (not os.path.isfile(os.path.join(self.gen_tpldir, fn)) ):
                    self.logger.debug("copy_templates: Copying template '{}' from plugin to smartVISU v{}".format(fn, self.smartvisu_version))
            shutil.copy2(os.path.join(self.sv_tpldir, 'index.html'), self.gen_tpldir)
            shutil.copy2(os.path.join(self.sv_tpldir, 'rooms.html'), self.gen_tpldir)

        else:  # sv v2.7 & v2.8
            # create output directory
            try:
                os.mkdir(self.gen_tpldir)
            except:
                pass
            # Open file for twig import statements (for root.html)
            for fn in os.listdir(self.shng_tpldir):
                if (self.overwrite_templates) or (not os.path.isfile(os.path.join(self.gen_tpldir, fn)) ):
                    self.logger.debug("copy_templates: Copying template '{}' from plugin to smartVISU v{}".format(fn, self.smartvisu_version))
                    try:
                        shutil.copy2( os.path.join(self.shng_tpldir, fn), self.gen_tpldir )
                    except Exception as e:
                        self.logger.error("Could not copy {0} from {1} to {2}".format(fn, self.shng_tpldir, self.gen_tpldir))
        return


