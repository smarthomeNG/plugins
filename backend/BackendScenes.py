#!/usr/bin/env python3
# -*- coding: utf8 -*-
#########################################################################
# Copyright 2016-       René Frieß                  rene.friess@gmail.com
#                       Martin Sinn                         m.sinn@gmx.de
#                       Bernd Meiners
#                       Christian Strassburg          c.strassburg@gmx.de
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

import cherrypy

class BackendScenes:


    # -----------------------------------------------------------------------------------
    #    SCENES
    # -----------------------------------------------------------------------------------

    @cherrypy.expose
    def scenes_html(self):

        from lib.scene import Scenes
        get_param_func = getattr(Scenes, "get_instance", None)
        if callable(get_param_func):
            supported = True
            self.scenes = Scenes.get_instance()
            scene_list = self.scenes.get_loaded_scenes()

            disp_scene_list = []
            for scene in scene_list:
                scene_dict = {}
                scene_dict['path'] = scene
                scene_dict['name'] = str(self._sh.return_item(scene))

                action_list = self.scenes.get_scene_actions(scene)
                scene_dict['value_list'] = action_list
                scene_dict[scene] = action_list
            
                disp_action_list = []
                for value in action_list:
                    action_dict = {}
                    action_dict['action'] = value
                    action_dict['action_name'] = self.scenes.get_scene_action_name(scene, value)
                    action_list = self.scenes.return_scene_value_actions(scene, value)
                    for action in action_list:
                        if not isinstance(action[0], str):
                            action[0] = action[0].id()
                    action_dict['action_list'] = sorted(action_list)

                    disp_action_list.append(action_dict)
                scene_dict['values'] = disp_action_list
                self.logger.info("scenes_html: disp_action_list for scene {} = {}".format(scene, disp_action_list))
                
                disp_scene_list.append(scene_dict)
        else:
            supported = False
        return self.render_template('scenes.html', supported=supported, scene_list=disp_scene_list)



