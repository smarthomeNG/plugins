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

    valid_sv_page_entries = ['room', 'overview', 'separator', 'seperator',
                             'category', 'cat_overview', 'cat_separator', 'cat_seperator',
                             'room_lite', 'sv_overview']

    def __init__(self, plugin_instance, visu_definition=None):
        self.items = Items.get_instance()

        self.plugin_instance = plugin_instance
        self.logger = plugin_instance.logger
        self._sh = plugin_instance._sh

        # get plugin parameter values
        self.smartvisu_dir = plugin_instance.smartvisu_dir
        self.smartvisu_version = plugin_instance.smartvisu_version
        self.overwrite_templates = plugin_instance.overwrite_templates
        self.visu_style = plugin_instance.visu_style.lower()
        if self.visu_style not in ['std', 'blk']:
            self.visu_style = 'std'
            self.logger.warning("SmartVisuGenerator: visu_style '{0}' unknown, using visu_style '{1}'".format(plugin_instance.visu_style, self.visu_style))
        self.list_deprecated_warnings = plugin_instance.list_deprecated_warnings


        self.logger.info("Generating pages for smartVISU v{}".format(self.smartvisu_version))

        # get template directory of this plugin
        self.thisplg_dir = os.path.dirname(os.path.abspath(__file__))
        self.shng_tpldir = os.path.join(self.thisplg_dir, 'tplNG')

        self.sv_tpldir = os.path.join(self.smartvisu_dir, 'pages', '_template')
        self.gen_tpldir = os.path.join(self.smartvisu_dir, 'pages', 'base', 'tplNG')
        if self.smartvisu_version >= '2.9':
            self.gen_tpldir = os.path.join(self.smartvisu_dir, 'dropins')

        self.tmpdir = os.path.join(self.smartvisu_dir, 'temp')
        self.pages_dir = os.path.join(self.smartvisu_dir, 'pages', 'smarthome')

        self.copy_templates()

        self.navigation = {'room': [], 'category': [], 'room_lite': []}          # dict of list of dicts
        if visu_definition is not None:
            self.initialize_visu_navigation(visu_definition.get('navigation', None))

        self.pages()
        self.logger.info("Generating pages for smartVISU v{} End".format(self.smartvisu_version))

    def initialize_visu_navigation(self, nav_config):
        """
        Initialize the navigation structure from the given nav_config,
        which is read from the configuration file ../etc/visu.yaml

        :param nav_config: dict with configuration info
        """
        if nav_config is None:
            return

        self.initialize_visu_menu(nav_config, 'room')
        self.initialize_visu_menu(nav_config, 'category')
        self.initialize_visu_menu(nav_config, 'room_lite')
        return

    def initialize_visu_menu(self, nav_config, menu):
        """

        :param nav_config: dict with configuration info
        :param menu: 'room', 'category' or 'room_lite'
        """
        for entry in nav_config.get(menu, {}):
            self.logger.debug("initialize_visu_menu: '{}' entry={}".format(menu, entry))
            name = entry.get('name', '')
            display_name = entry.get('display_name', '')
            item_path = entry.get('path', '')
            separator = entry.get('separator', False)
            img = entry.get('img', None)
            if name != '':
                menu_entry = self.create_menuentry(menu, name, display_name, item_path, separator, img, entry.get('nav_aside', None), entry.get('nav_aside2', None), True)
                self.add_menuentry_to_list(menu, menu_entry)
            self.logger.debug("initialize_visu_menu: '{}' menu_entry={}".format(menu, menu_entry))


    def check_heading_buttons_attribute(self, room):
        """
        Test if the attribute contains a list of three lists
        """
        if 'sv_heading_buttons' in room.conf:
            heading_buttons = room.conf['sv_heading_buttons']
            if not isinstance(heading_buttons, list) or len(heading_buttons) < 2:
                self.logger.warning(f"sv_page '{room}': Fehlerhafte Definition im Attribut 'sv_heading_buttons'")
                return 0

            heading_buttons_text = heading_buttons[0]
            if not isinstance(heading_buttons_text, list):
                self.logger.warning(f"sv_page '{room}': Fehlerhafte Definition im Attribut 'sv_heading_buttons' - Text Definition ist keine Liste")
                return 0

            heading_buttons_room = heading_buttons[1]
            if not isinstance(heading_buttons_room, list):
                self.logger.warning(f"sv_page '{room}': Fehlerhafte Definition im Attribut 'sv_heading_buttons' - Seitennamen sind keine Liste")
                return 0

            #heading_buttons_icon = heading_buttons[2]

        return len(heading_buttons_text)


    def handle_heading_buttons(self, room):
        """
        Handling of sv_heading_buttons attribute
        """
        heading = ''

        # Check if attribute is formatting correct
        if 'sv_heading_buttons' in room.conf:
            page_type = room.conf['sv_page']
            button_count = self.check_heading_buttons_attribute(room)
            if button_count > 0:
                heading_buttons_text = room.conf['sv_heading_buttons'][0]
                heading_buttons_room = room.conf['sv_heading_buttons'][1]
                if len(room.conf['sv_heading_buttons']) > 2:
                    heading_buttons_icon = room.conf['sv_heading_buttons'][2]
                else:
                    heading_buttons_icon = []          # create empty list, if no icons are defined

                # Determine activ Button and set html class for it
                heading_buttons_active = [''] * button_count

                for i in range (0, len(heading_buttons_room)):
                    heading_buttons_room[i] = heading_buttons_room[i].replace(' ', '_').replace('/', '_')
                for i in range(0, len(heading_buttons_active)):
                    if heading_buttons_room[i] == room.property.name.replace(' ', '_').replace('/', '_'):
                        heading_buttons_active[i] = 'ui-btn-active ui-state-persist'   # active = 'ui-btn-active ui-state-persist'
                    if len(heading_buttons_icon) == 0 and len(heading_buttons_active) < 4:
                        heading_buttons_active[i] += ' ui-btn-largetext'   # active = 'ui-btn-active ui-state-persist'

                # Replace placeholders in heading-template
                if len(heading_buttons_icon) == 0:
                    tpl_fn = 'heading_' + str(button_count) + 'textbuttons.html'
                    heading = self.parse_tpl_from_file(tpl_fn, [('{{ text1 }}', heading_buttons_text[0]),
                                                                ('{{ page1 }}', page_type + '.' + heading_buttons_room[0]),
                                                                ('{{ activeclass1 }}', heading_buttons_active[0])])
                    heading = self.parse_tpl(heading, [('{{ text2 }}', heading_buttons_text[1]),
                                                       ('{{ page2 }}', page_type + '.' + heading_buttons_room[1]),
                                                       ('{{ activeclass2 }}', heading_buttons_active[1])])

                    if button_count > 2:
                        heading = self.parse_tpl(heading, [('{{ text3 }}', heading_buttons_text[2]),
                                                           ('{{ page3 }}', page_type + '.' + heading_buttons_room[2]),
                                                           ('{{ activeclass3 }}', heading_buttons_active[2])])

                else:
                    tpl_fn = 'heading_' + str(button_count) + 'buttons.html'
                    heading = self.parse_tpl_from_file(tpl_fn, [('{{ text1 }}', heading_buttons_text[0]),
                                                                ('{{ page1 }}', page_type + '.' + heading_buttons_room[0]),
                                                                ('{{ navicon1 }}', heading_buttons_icon[0]),
                                                                ('{{ activeclass1 }}', heading_buttons_active[0])])
                    heading = self.parse_tpl(heading, [('{{ text2 }}', heading_buttons_text[1]),
                                                       ('{{ page2 }}', page_type + '.' + heading_buttons_room[1]),
                                                       ('{{ navicon2 }}', heading_buttons_icon[1]),
                                                       ('{{ activeclass2 }}', heading_buttons_active[1])])

                    if button_count > 2:
                        heading = self.parse_tpl(heading, [('{{ text3 }}', heading_buttons_text[2]),
                                                           ('{{ page3 }}', page_type + '.' + heading_buttons_room[2]),
                                                           ('{{ navicon3 }}', heading_buttons_icon[2]),
                                                           ('{{ activeclass3 }}', heading_buttons_active[2])])

                    if button_count > 3:
                        heading = self.parse_tpl(heading, [('{{ text4 }}', heading_buttons_text[3]),
                                                           ('{{ page4 }}', page_type + '.' + heading_buttons_room[3]),
                                                           ('{{ navicon4 }}', heading_buttons_icon[3]),
                                                           ('{{ activeclass4 }}', heading_buttons_active[3])])

                    if button_count > 4:
                        heading = self.parse_tpl(heading, [('{{ text5 }}', heading_buttons_text[4]),
                                                           ('{{ page5 }}', page_type + '.' + heading_buttons_room[4]),
                                                           ('{{ navicon5 }}', heading_buttons_icon[4]),
                                                           ('{{ activeclass5 }}', heading_buttons_active[4])])

        return heading


    def handle_heading_attributes(self, room):
        """
        Handling of sv_heading_left, sv_heading_center and sv_heading_right attributes
        """
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

        heading = ''
        if heading_right != '' or heading_center != '' or heading_left != '':
            heading = self.parse_tpl_from_file('heading.html', [('{{ visu_heading_right }}', heading_right), ('{{ visu_heading_center }}', heading_center), ('{{ visu_heading_left }}', heading_left)])
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
            if blocksize not in ['1', '2', '3']:
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


    def create_page(self, room, menu_entry):
        """
        Interpretation of the room-specific item-attributes.
        This routine is called once per 'sv_page'.

        :param room: Items (with room configuration)

        :return: html code to be included in the visu file for the room
        :rtype: str
        """
        block_style = 'std'  # 'std' or 'noh'
        widgetblocktemplate = 'widgetblock_' + self.visu_style + '_' + block_style + '.html'
        # for set of two blocks in a widget:
        widgetblocktemplate2 = 'widgetblock2_' + self.visu_style + '_' + block_style + '.html'
        widgets = ''

        heading = self.handle_heading_buttons(room)
        if heading == '':
            heading = self.handle_heading_attributes(room)

        if 'sv_widget' in room.conf:
            items = [room]
        else:
            items = []

        if (room.conf['sv_page'] == 'room') or (room.conf['sv_page'] == 'room_lite'):
            items.extend(self.items.find_children(room, 'sv_widget'))
        elif room.conf['sv_page'] == 'category':
            items.extend(self.items.find_children(room, 'sv_widget'))
        elif room.conf['sv_page'] == 'overview':
            items.extend(self.items.find_items('sv_item_type'))
        menu_entry['display_name'] = room.conf.get('sv_display_name', str(room))

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
                    widgets += self.parse_tpl_from_file(widgetblocktemplate, [('{{ visu_name }}', str(item)), ('{{ visu_img }}', img), ('{{ visu_widget }}', widget), ('item.name', str(item)), ("'item", "'" + item.property.path)])
            else:
                blocksize = self.get_widgetblocksize(item)

                widget = self.get_attribute('sv_widget', item)
                widget2 = self.get_attribute('sv_widget2', item)
                if widget2 == '':
                    name1 = self.get_attribute('sv_name1', item)
                    if name1 == '':
                        name1 = item
                    widgets += self.parse_tpl_from_file(widgetblocktemplate, [('{{ visu_name }}', str(name1)), ('{{ blocksize }}', str(blocksize)), ('{{ visu_img }}', img), ('{{ visu_widget }}', widget), ('item.name', str(item)), ("'item", "'" + item.property.path)])
                else:
                    name2 = self.get_attribute('sv_name2', item)
                    widgets += self.parse_tpl_from_file(widgetblocktemplate2, [('{{ visu_name }}', str(name1)), ('{{ visu_name2 }}', str(name2)), ('{{ visu_img }}', img), ('{{ visu_widget }}', widget), ('{{ visu_widget2 }}', widget2), ('item.name', str(item)), ("'item", "'" + item.property.path)])

        menu_entry['heading'] = heading
        menu_entry['content'] += widgets
        return r


    def pages(self):
        if not self.remove_oldpages():
            return

        for item in self.items.find_items('sv_page'):
            if ((item.conf['sv_page'] == 'overview') or (item.conf['sv_page'] == 'cat_overview')) and (not 'sv_overview' in item.conf):
                self.logger.error("missing sv_overview for {0}".format(item.property.path))
                continue

            self.plugin_instance.test_item_for_deprecated_widgets(item)

            # Add entry to navigation list for page

            if not item.conf['sv_page'] in self.valid_sv_page_entries:
                self.logger.warning(f"{item.property.path}: 'sv_page' attribute contains unknown value '{item.conf['sv_page']}'")
            else:
                # find out to which navigation menu the page belongs
                separator = False
                menu = item.conf['sv_page']
                if menu == 'overview':
                    menu = 'room'
                elif menu == 'cat_overview':
                    menu = 'category'
                elif menu in ['separator', 'seperator']:
                    menu = 'room'
                    separator = True
                elif menu in ['cat_separator', 'cat_seperator']:
                    menu = 'category'
                    separator = True

                # build nav_aside code

                nav_aside = ''
                nav_aside2 = ''
                if 'sv_nav_aside' in item.conf:
                    if isinstance(item.conf['sv_nav_aside'], list):
                        nav_aside += ', '.join(item.conf['sv_nav_aside'])
                    else:
                        nav_aside += item.conf['sv_nav_aside']
                if 'sv_nav_aside2' in item.conf:
                    if isinstance(item.conf['sv_nav_aside2'], list):
                        nav_aside2 += ', '.join(item.conf['sv_nav_aside2'])
                    else:
                        nav_aside2 += item.conf['sv_nav_aside2']

                display_name = item.conf.get('sv_display_name', str(item))
                menu_entry = self.create_menuentry(menu=menu, entry_name=str(item), display_name=display_name, item_path=item.property.path, separator=separator,
                                                   img_name=self.get_attribute('sv_img', item), nav_aside=nav_aside, nav_aside2=nav_aside2)

                self.create_page(item, menu_entry)

                # determine, if generated page should be added to the navigation
                menu_entry['add_to_nav_menu'] = item.conf.get('sv_page_in_navi', True)
                self.add_menuentry_to_list(menu, menu_entry)

        # after processing all pages: write navigation files
        self.write_navigation_and_pages('room', 'rooms_menu.html')
        self.write_navigation_and_pages('category', 'category_menu.html')
        self.write_navigation_and_pages('room_lite', 'roomlite_nav.html')

        # copy templates from plugin's template folder to pages folder for templates
        self.copy_tpl('rooms.html')
        self.copy_tpl('rooms_lite.html')
        self.copy_tpl('category.html')
        self.copy_tpl('index.html')
        self.copy_tpl('visu.css')
        self.copy_tpl('infoblock.html')


#########################################################################

    def create_menuentry(self, menu, entry_name, display_name, item_path, separator, img_name, nav_aside, nav_aside2, from_navconfig=False):
        for menu_entry in self.navigation[menu]:
            if menu_entry['name'] == entry_name:
                if menu_entry.get('img', '') == '' and menu_entry.get('img_set', False) is False:
                    menu_entry['img'] = img_name
                if menu_entry['item_path'] == '':
                    menu_entry['item_path'] = item_path
                if menu_entry.get('nav_aside', '') == '' and menu_entry.get('nav_aside_set', False) is False:
                    menu_entry['nav_aside'] = nav_aside
                if menu_entry.get('nav_aside2', '') == '' and menu_entry.get('nav_aside2_set', False) is False:
                    menu_entry['nav_aside2'] = nav_aside2
                return menu_entry

        menu_entry = {}
        menu_entry['name'] = entry_name
        menu_entry['display_name'] = display_name
        menu_entry['item_path'] = item_path
        menu_entry['separator'] = separator
        menu_entry['page'] = menu + '.' + entry_name
        for ch in [' ', ':', '/', '\\']:
            if ch in menu_entry['page']:
                menu_entry['page'] = menu_entry['page'].replace(ch, '_')
        menu_entry['heading'] = ''
        menu_entry['content'] = ''

        if not from_navconfig:
            menu_entry['img'] = img_name
            menu_entry['nav_aside'] = nav_aside
            menu_entry['nav_aside2'] = nav_aside2
        else:
            menu_entry['img'] = ''
            menu_entry['img_set'] = False
            menu_entry['nav_aside'] = ''
            menu_entry['nav_aside_set'] = False
            menu_entry['nav_aside2'] = ''
            menu_entry['nav_aside2_set'] = False

            if img_name is not None:
                menu_entry['img'] = img_name
                menu_entry['img_set'] = True
            if nav_aside is not None:
                menu_entry['nav_aside'] = nav_aside
                menu_entry['nav_aside_set'] = True
            if nav_aside2 is not None:
                menu_entry['nav_aside2'] = nav_aside2
                menu_entry['nav_aside2_set'] = True

        return menu_entry

    def add_menuentry_to_list(self, menu, menu_entry):
        for entry in self.navigation[menu]:
            if entry['name'] == menu_entry['name']:
                self.logger.debug("{}: add_menuentry_to_list: Found menu {}, entry {}".format(self.plugin_instance.get_instance_name(), menu, menu_entry['name']))
                return

        self.navigation[menu].append(menu_entry)
        return

#########################################################################

    def build_and_write_page_file(self, menu, menu_entry):
        """
        Build and write file for a single room
        """

        # build page for a single room
        page = self.parse_tpl_from_file(menu + '_page.html',[('{{ visu_name }}', menu_entry['display_name']), ('{{ visu_img }}', menu_entry['img'])] )
        #if menu_entry['page'] == 'room.Kochen':
        #    self.logger.notice(f"'build_and_write_page_file: {menu_entry['page']}' heading: {menu_entry['heading']}")
        #    #self.logger.notice(f"build_and_write_page_file: '{menu_entry['page']}' visu_widgets: {menu_entry['content']}")
        page = self.parse_tpl(page, [('{{ visu_heading }}', menu_entry['heading'])] )
        page = self.parse_tpl(page, [('{{ visu_widgets }}', menu_entry['content'])] )

        # write page to file
        self.logger.debug(f"build_and_write_page_file: Writing page '{menu_entry['page'] + '.html'}'")
        self.write_parseresult(menu_entry['page'] + '.html', page)

        return


    def write_navigation_and_pages(self, menu, navigation_file):

        #self.logger.notice(f"write_navigation_and_pages: {menu=}, {navigation_file=}")
        nav_list = ''
        for menu_entry in self.navigation[menu]:
            parse_list = [('{{ visu_page }}', menu_entry['page']), ('{{ visu_name }}', menu_entry['display_name']),
                          ('{{ visu_img }}', menu_entry['img']),
                          ('{{ visu_aside }}', menu_entry['nav_aside']),
                          ('{{ visu_aside2 }}', menu_entry['nav_aside2']),
                          ('item.name', menu_entry['name']), ("'item", "'" + menu_entry['item_path'])
                          ]

            # build navigation list, excluding pages with add_to_nav_menu == False
            if  menu_entry.get('add_to_nav_menu', True):
                if menu_entry['separator'] is True:
                    nav_list += self.parse_tpl_from_file('navi_sep.html', [('{{ name }}', menu_entry['name'])])
                else:
                    if self.smartvisu_version >= '3.3' and menu_entry['img'].lower().endswith('.svg'):
                        #self.logger.notice(f" - nav_list svg entry: {menu_entry['img']=}, parse_list={parse_list}")
                        nav_list += self.parse_tpl_from_file('navi_svg.html', parse_list)
                    else:
                        #self.logger.notice(f" - nav_list png entry: {menu_entry['img']=}, parse_list={parse_list}")
                        self.logger.debug(f" - nav_list entry: entry={self.parse_tpl_from_file('navi.html', parse_list)}")
                        nav_list += self.parse_tpl_from_file('navi.html', parse_list)


            # build page code
            if menu_entry['separator'] is False:
                self.build_and_write_page_file(menu, menu_entry)

        # write navigation menu file
        self.write_parseresult(navigation_file, self.parse_tpl_from_file('navigation.html', [('{{ visu_navis }}', nav_list)]))

        return

    # def write_navigation_file(self, menu, template_file, navigation_file):
    #
    #     nav_lis = ''
    #     for entry in self.navigation[menu]:
    #         nav_lis += entry['html']
    #
    #     nav = self.parse_tpl_from_file(template_file, [('{{ visu_navis }}', nav_lis)])
    #     self.write_parseresult(navigation_file, nav)
    #     return

    def parse_tpl(self, template, replace):
        """
        Replace strings in a template

        :param template: template
        :param replace: list of sets, where each set contains the string to replace and the replacement string

        :return: resulting string with replacement(s)
        """
        for s, r in replace:
            if r is None:
                rs = ''
            else:
                rs = r
                template = template.replace(s, rs)

        return template


    def parse_tpl_from_file(self, template_file, replace):
        """
        Read template file and replace strings in that template

        :param template_file: template filename
        :param replace:       list of sets, where each set contains the string to replace and the replacement string

        :return: resulting string with replacement(s)
        """
        self.logger.debug(f"try to parse template file '{template_file}'")
        try:
            with open(os.path.join(self.gen_tpldir, template_file), 'r', encoding='utf-8') as f:
                tpl = f.read()
                tpl = tpl.lstrip('\ufeff')  # remove BOM
        except Exception as e:
            self.logger.error(f"Could not read template file '{template_file}': {e}")
            return ''

        tpl = self.parse_tpl(tpl, replace)

        return tpl


    def write_parseresult(self, htmlfile, parseresult):
        """
        Write the parsed result to the pages directory in smartVISU
        """
        try:
            with open(os.path.join(self.pages_dir, htmlfile), 'w') as f:
                f.write(parseresult)
        except Exception as e:
            self.logger.warning(f"Could not write to {self.pages_dir}/{htmlfile}: {e}")


    def copy_tpl(self, tplname, destname=''):
        if destname == '':
            destname = tplname
        try:
            shutil.copy(os.path.join(self.gen_tpldir, tplname), os.path.join(self.pages_dir, destname))
        except Exception as e:
            self.logger.error(f"Could not copy {tplname} from {self.gen_tpldir} to {self.pages_dir}")


#########################################################################

    def remove_oldpages(self):
        """
        Remove the pages that were generated during a previous run of this plugin
        """
        if not os.path.isdir(self.tmpdir):
            self.logger.warning(f"Could not find directory: {self.tmpdir}")
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
                self.logger.warning(f"Could not delete directory {dp}: {e}")
        # create output directory
        try:
            os.mkdir(self.pages_dir)
        except:
            pass
        # remove old dynamic files
        if not os.path.isdir(self.pages_dir):
            self.logger.warning(f"Could not find/create directory: {self.pages_dir}")
            return False
        for fn in os.listdir(self.pages_dir):
            fp = os.path.join(self.pages_dir, fn)
            try:
                if os.path.isfile(fp):
                    os.unlink(fp)
            except Exception as e:
                self.logger.warning(f"Could not delete file {fp}: {e}")
        return True


#########################################################################

    def copy_templates(self):
        """
        Copy templates from this plugin to the location inside smartVISU from which they are
        used during the generation of the visu pages
        """
        if not os.path.isdir(self.shng_tpldir):
            self.logger.warning(f"copy_templates: Could not find source directory {self.shng_tpldir}")
            return

        if self.smartvisu_version >= '2.9':
            for fn in os.listdir(self.shng_tpldir):
                if (self.overwrite_templates) or (not os.path.isfile(os.path.join(self.gen_tpldir, fn))):
                    self.logger.debug(f"copy_templates: Copying template '{fn}' from plugin to smartVISU v{self.smartvisu_version} ({self.gen_tpldir})")
                    shutil.copy2(os.path.join(self.shng_tpldir, fn), self.gen_tpldir)
            shutil.copy2(os.path.join(self.sv_tpldir, 'index.html'), self.pages_dir)
            shutil.copy2(os.path.join(self.sv_tpldir, 'rooms.html'), self.pages_dir)
            shutil.copy2(os.path.join(self.sv_tpldir, 'visu.css'), self.pages_dir)
            if self.smartvisu_version >= '3.2':
                shutil.copy2(os.path.join(self.sv_tpldir, 'infoblock.html'), self.gen_tpldir)

        else:  # sv v2.7 & v2.8
            # create output directory
            try:
                os.mkdir(self.gen_tpldir)
            except:
                pass
            # Open file for twig import statements (for root.html)
            for fn in os.listdir(self.shng_tpldir):
                if (self.overwrite_templates) or (not os.path.isfile(os.path.join(self.gen_tpldir, fn))):
                    self.logger.debug(f"copy_templates: Copying template '{fn}' from plugin to smartVISU v{self.smartvisu_version}")
                    try:
                        shutil.copy2(os.path.join(self.shng_tpldir, fn), self.gen_tpldir)
                    except Exception as e:
                        self.logger.error(f"Could not copy {fn} from {self.shng_tpldir} to {self.gen_tpldir}")
        return
