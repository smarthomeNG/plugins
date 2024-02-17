#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2020-      <gruberth>                                <EMAIL>
#########################################################################
#  This file is part of SmartHomeNG.
#  https://www.smarthomeNG.de
#  https://knx-user-forum.de/forum/supportforen/smarthome-py
#
#  Plugin to send web push messages to clients.
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
#
#########################################################################
import os
import json
import sqlite3
from lib.module import Modules
from lib.model.smartplugin import *
import cherrypy
from datetime import datetime

import warnings
from cryptography.utils import CryptographyDeprecationWarning

with warnings.catch_warnings():
    warnings.filterwarnings('ignore', category=CryptographyDeprecationWarning)
    import py_vapid
    from pywebpush import webpush, WebPushException
    from cryptography.hazmat.primitives import serialization


class WebPush(SmartPlugin):
    """
    Main class of the Plugin. Does all plugin specific stuff and provides
    the update functions for the items

    HINT: Please have a look at the SmartPlugin class to see which
    class properties and methods (class variables and class functions)
    are already available!
    """

    PLUGIN_VERSION = '1.1.0'  # (must match the version specified in plugin.yaml), use '1.0.0' for your initial plugin Release

    ITEM_COMMUNICATION = "webpush_communication"
    ITEM_CONFIG = "webpush_config"

    VALID_COMMUNICATIONS = ['fromclient']
    VALID_CONFIGS = ['grouplist', 'publickey']

    VALID_CMDS = ['subscribe', 'unsubscribe']

    def __init__(self, sh):
        """
        Initalizes the plugin.

        If you need the sh object at all, use the method self.get_sh() to get it. There should be almost no need for
        a reference to the sh object any more.

        Plugins have to use the new way of getting parameter values:
        use the SmartPlugin method get_parameter_value(parameter_name). Anywhere within the Plugin you can get
        the configured (and checked) value for a parameter by calling self.get_parameter_value(parameter_name). It
        returns the value in the datatype that is defined in the metadata.
        """

        # Call init code of parent class (SmartPlugin)
        super().__init__()

        # get the parameters for the plugin (as defined in metadata plugin.yaml):
        self.groupList = self.get_parameter_value('grouplist')
        self.varpath = self.get_parameter_value('varpath')

        self.groupListItem = None
        self.publicKeyItem = None
        self.fromClientItem = None

        self.alive = False

        self.pluginVarPath = self.varpath + "/webpush/"
        self.databasePath = self.pluginVarPath + "webpush_database.txt"
        self.keyFilePath = self.pluginVarPath + "webpush_private_key.pem"

        if not os.path.exists(self.pluginVarPath):
            os.mkdir(self.pluginVarPath)

        self.initDatabase()

        self.vapid = py_vapid.Vapid().from_file(self.keyFilePath)
        raw_pub = self.vapid.public_key.public_bytes(
            serialization.Encoding.X962,
            serialization.PublicFormat.UncompressedPoint
        )
        self.publicKey = py_vapid.b64urlencode(raw_pub)

        self.logger.info("Application Server Key: {0}".format(self.publicKey))

        # On initialization error use:
        #   self._init_complete = False
        #   return

        # if plugin should start even without web interface
        self.init_webinterface()
        # if plugin should not start without web interface
        # if not self.init_webinterface():
        #     self._init_complete = False

        return

    def run(self):
        """
        Run method for the plugin
        """
        # if you need to create child threads, do not make them daemon = True!
        # They will not shut down properly. (It's a python bug)
        self.logger.debug("Run method called")

        alive = True

        if self.groupListItem is None:
            self.logger.warning("Item webpush_config: grouplist needed!")
            alive = False
        if self.publicKeyItem is None:
            self.logger.warning("Item webpush_config: publickey needed!")
            alive = False
        if self.fromClientItem is None:
            self.logger.warning("Item webpush_communication: fromclient needed!")
            alive = False

        self.alive = alive

    def stop(self):
        """
        Stop method for the plugin
        """
        self.logger.debug("Stop method called. Shutting down...")
        self.alive = False

    def parse_item(self, item):
        """
        Default plugin parse_item method. Is called when the plugin is initialized.
        The plugin can, corresponding to its attribute keywords, decide what to do with
        the item in the future, like adding it to an internal array for future reference
        :param item:    The item to process.
        :return:        If the plugin needs to be informed of an items change you should return a call back function
                        like the function update_item down below. An example when this is needed is the knx plugin
                        where parse_item returns the update_item function when the attribute knx_send is found.
                        This means that when the items value is about to be updated, the call back function is called
                        with the item, caller, source and dest as arguments and in case of the knx plugin the value
                        can be sent to the knx with a knx write function within the knx plugin.
        """

        if self.has_iattr(item.conf, self.ITEM_COMMUNICATION):
            self.logger.debug("parse COMMUNICATION item: {}".format(item))

            value = self.get_iattr_value(item.conf, self.ITEM_COMMUNICATION).lower()
            if value in self.VALID_COMMUNICATIONS:
                self.logger.debug("adding valid info item {0} to wachlist {1}={2} ".format(
                    item, self.ITEM_COMMUNICATION, item.conf[self.ITEM_COMMUNICATION]))

                if value == self.VALID_COMMUNICATIONS[0]:
                    if self.fromClientItem is not None:
                        self.logger.error("Multiple entry of communication item '{0}'. Skipping this.".format(value))
                        return
                    else:
                        self.fromClientItem = item
                return self.update_item
            else:
                self.logger.error("communication '{0}' invalid, use one of {1}".format(value,
                                                                                       self.VALID_COMMUNICATIONS))

        if self.has_iattr(item.conf, self.ITEM_CONFIG):
            self.logger.debug("parse CONFIG item: {}".format(item))

            value = self.get_iattr_value(item.conf, self.ITEM_CONFIG).lower()
            if value in self.VALID_CONFIGS:
                self.logger.debug("adding valid config item {0} to wachlist {1}={2} ".format(
                    item, self.ITEM_CONFIG, item.conf[self.ITEM_CONFIG]))

                if value == self.VALID_CONFIGS[0]:
                    if self.groupListItem is not None:
                        self.logger.error("Multiple entry of config item '{0}'. Skipping this.".format(value))
                        return
                    else:
                        self.groupListItem = item
                        self.groupListItem(self.groupList, self.get_shortname())
                elif value == self.VALID_CONFIGS[1]:
                    if self.publicKeyItem is not None:
                        self.logger.error("Multiple entry of config item '{0}'. Skipping this.".format(value))
                        return
                    else:
                        self.publicKeyItem = item
                        self.publicKeyItem(self.publicKey, self.get_shortname())

                return
            else:
                self.logger.error("config '{0}' invalid, use one of {1}".format(value, self.VALID_CONFIGS))

    def parse_logic(self, logic):
        """
        Default plugin parse_logic method
        """
        pass

    def update_item(self, item, caller=None, source=None, dest=None):
        """
        Item has been updated

        This method is called, if the value of an item has been updated by SmartHomeNG.
        It should write the changed value out to the device (hardware/interface) that
        is managed by this plugin.

        :param item: item to be updated towards the plugin
        :param caller: if given it represents the callers name
        :param source: if given it represents the source
        :param dest: if given it represents the dest
        """

        if self.alive and caller != self.get_shortname():
            # code to execute if the plugin is not stopped
            # and only, if the item has not been changed by this plugin:
            item_value = "{0}".format(item())
            self.logger.info(
                "Update item: {0}, item has been changed outside this plugin to value={1}".format(item.property.path,
                                                                                                  item_value))
            if self.has_iattr(item.conf, self.ITEM_COMMUNICATION):
                self.logger.debug(
                    "update_item was called with item '{}' from caller '{}', source '{}' and dest '{}'".format(item,
                                                                                                               caller,
                                                                                                               source,
                                                                                                               dest))

                if item == self.fromClientItem:
                    # clear communication item
                    item('', self.get_shortname())
                    # process stored message
                    self.processMessageFromClient(item_value)

    # ------------------------------------------
    #    Methods of the plugin
    # ------------------------------------------

    def initDatabase(self):
        # create database if not exists
        dbConn = sqlite3.connect(self.databasePath)
        c = dbConn.cursor()
        c.execute("CREATE TABLE IF NOT EXISTS subscriptions"
                  "([id] INTEGER PRIMARY KEY,"
                  "[sessionId] varchar(255) NOT NULL,"
                  "[subscription] varchar(512) NOT NULL,"
                  "[subscriptiongroup] varchar(255) NOT NULL)")
        dbConn.commit()

        # delete all entries for groups wich are still in database but not in plugin conifg anymore
        sql = "SELECT subscriptiongroup FROM subscriptions GROUP BY subscriptiongroup"
        c.execute(sql)
        dbgrouptuplelist = c.fetchall()

        dbgrouplist = []
        for dbgrouptuple in dbgrouptuplelist:
            dbgrouplist.append(dbgrouptuple[0])
        diffgrouplist = list(set(dbgrouplist).difference(self.groupList))

        for diffgroup in diffgrouplist:
            sql = "DELETE FROM subscriptions WHERE subscriptiongroup = '{0}'".format(diffgroup)
            c.execute(sql)
            dbConn.commit()

        dbConn.close()

    def processMessageFromClient(self, msg):
        # subscription message should look like:
        # msg = {"cmd": "subscribe",
        #        "sessionId": "321435434",
        #        "groups": ["alarm", "info"],
        #        "subscription": {"sfdg": "sdfgfdss", "kmjm": "sshgs"}
        #        }
        data = json.loads(msg)
        if data:
            if data["cmd"] in self.VALID_CMDS:
                self.logger.info("Executing cmd: {0} for sessionId: {1}".format(data["cmd"], data["sessionId"]))
                self.unsubscribeEntireSessionId(data["sessionId"])
                if data["cmd"] != "unsubscribe":
                    self.subscribeEntireSessionId(data["sessionId"], data["groups"], data["subscription"])
            else:
                self.logger.error("command '{0}' invalid, use one of {1}".format(data["cmd"], self.VALID_CMDS))

    def subscribe(self, sessionId, group, subscription):
        self.logger.info("Subscribing: {0} to {1}".format(sessionId, group))
        dbConn = sqlite3.connect(self.databasePath)
        c = dbConn.cursor()
        sql = 'INSERT INTO subscriptions (sessionId, subscription, subscriptiongroup) VALUES ("{0}", "{1}", "{2}")' \
            .format(sessionId, subscription, group)
        c.execute(sql)
        dbConn.commit()
        dbConn.close()

    def subscribeEntireSessionId(self, sessionId, groups, subscription):
        dbConn = sqlite3.connect(self.databasePath)
        c = dbConn.cursor()
        for group in groups:
            self.logger.info("Subscribing: {0} to {1}".format(sessionId, group))
            sql = 'INSERT INTO subscriptions (sessionId, subscription, subscriptiongroup) VALUES ("{0}", "{1}", "{2}")' \
                .format(sessionId, subscription, group)
            c.execute(sql)
        dbConn.commit()
        dbConn.close()

    def unsubscribe(self, sessionId, group):
        self.logger.info("Unsubscribing: {0} from {1}".format(sessionId, group))
        dbConn = sqlite3.connect(self.databasePath)
        c = dbConn.cursor()
        sql = "DELETE FROM subscriptions WHERE sessionId = '{0}' AND subscriptiongroup = '{1}'" \
            .format(sessionId, group)
        c.execute(sql)
        dbConn.commit()
        dbConn.close()

    def unsubscribeEntireSessionId(self, sessionId):
        self.logger.info("Unsubscribing: {0}".format(sessionId))
        dbConn = sqlite3.connect(self.databasePath)
        c = dbConn.cursor()
        sql = "DELETE FROM subscriptions WHERE sessionId = '{0}'" \
            .format(sessionId)
        c.execute(sql)
        dbConn.commit()
        dbConn.close()

    def unsubscribeBySubscription(self, subscription):
        self.logger.info("Unsubscribing by subscription: {0}".format(subscription))
        dbConn = sqlite3.connect(self.databasePath)
        c = dbConn.cursor()
        sql = 'DELETE FROM subscriptions WHERE subscription = "{0}"' \
            .format(subscription)
        c.execute(sql)
        dbConn.commit()
        dbConn.close()

    def unsubscribeAll(self):
        dbConn = sqlite3.connect(self.databasePath)
        self.logger.info("Unsubscribing all")
        c = dbConn.cursor()
        sql = "DELETE FROM subscriptions"
        c.execute(sql)
        dbConn.commit()
        dbConn.close()

    # ------------------------------------------
    #    Logic methods of the plugin
    # ------------------------------------------

    def sendPushNotification(self, msg, group, title="", url="", requireInteraction=True, icon="", badge="", image="",
                             silent=False, vibrate=[], ttl=604800, highpriority=True, returnval=True, timestamp=True):
        # options from https://developer.mozilla.org/en-US/docs/Web/API/ServiceWorkerRegistration/showNotification

        if timestamp:
            dt_string = datetime.now().strftime("[%d.%m.%Y %H:%M:%S]\n")
            msg = dt_string + msg

        data = {"body": msg,
                "title": title,
                "url": url,
                "requireInteraction": requireInteraction,
                "icon": icon,
                "badge": badge,
                "image": image,
                "silent": silent,
                "vibrate": vibrate}

        urgency = "normal"
        if highpriority:
            urgency = "high"
        headers = {"Urgency": urgency}

        dbConn = sqlite3.connect(self.databasePath)
        c = dbConn.cursor()
        sql = "SELECT subscription FROM subscriptions WHERE subscriptiongroup = '{0}'".format(group)
        c.execute(sql)
        subscriptionlist = c.fetchall()
        dbConn.close()

        counter = 0
        for subscription in subscriptionlist:
            sub = subscription[0].replace("\'", "\"").replace("None", "null")
            try:
                webpush(
                    subscription_info=json.loads(sub),
                    data=json.dumps(data),
                    vapid_private_key=self.vapid,
                    vapid_claims={
                        "sub": "mailto:YourNameHere@example.org",
                    },
                    ttl=ttl,
                    headers=headers
                )
                counter += 1
            except WebPushException as ex:
                self.logger.info("Send to {0} unsuccessfully...\n{1}".format(subscription[0], ex.message))
                # Mozilla returns additional information in the body of the response.
                if ex.response and ex.response.json():
                    extra = ex.response.json()
                    self.logger.info("Remote service replied with a {0}:{1}, {2}".format(
                        extra.code,
                        extra.errno,
                        extra.message))
                if '410' in ex.message:
                    self.unsubscribeBySubscription(subscription[0])

        self.logger.info("To {0}/{1} subscribers of group {2} successfully send.".format(
            counter, len(subscriptionlist), group))

        return returnval

    # ------------------------------------------
    #    Webinterface methods of the plugin
    # ------------------------------------------

    # webinterface init method
    def init_webinterface(self):
        """"
        Initialize the web interface for this plugin

        This method is only needed if the plugin is implementing a web interface
        """
        try:
            self.mod_http = Modules.get_instance().get_module(
                'http')  # try/except to handle running in a core version that does not support modules
        except:
            self.mod_http = None
        if self.mod_http == None:
            self.logger.error("Not initializing the web interface")
            return False

        import sys
        if not "SmartPluginWebIf" in list(sys.modules['lib.model.smartplugin'].__dict__):
            self.logger.warning("Web interface needs SmartHomeNG v1.5 and up. Not initializing the web interface")
            return False

        # set application configuration for cherrypy
        webif_dir = self.path_join(self.get_plugin_dir(), 'webif')
        config = {
            '/': {
                'tools.staticdir.root': webif_dir,
            },
            '/static': {
                'tools.staticdir.on': True,
                'tools.staticdir.dir': 'static'
            }
        }

        # Register the web interface as a cherrypy app
        self.mod_http.register_webif(WebInterface(webif_dir, self),
                                     self.get_shortname(),
                                     config,
                                     self.get_classname(), self.get_instance_name(),
                                     description='')

        return True

    def getAllSubscriptionGroups(self):
        return self.groupList

    def getSubscriptionGroupCount(self):
        return len(self.groupList)

    def getSubscritionsPerGroup(self):
        dbConn = sqlite3.connect(self.databasePath)
        c = dbConn.cursor()
        sql = "SELECT subscriptiongroup, COUNT(id) FROM subscriptions GROUP BY subscriptiongroup"
        c.execute(sql)
        groupcounttuplelist = c.fetchall()
        dbConn.close()

        groupcountlist = []
        for group in self.groupList:
            groupcountlist.append([group, 0])
        for dbgroup, dbgroupcount in groupcounttuplelist:
            for group in groupcountlist:
                if group[0] == dbgroup:
                    group[1] = dbgroupcount
                    break

        return groupcountlist

    def getPublicKey(self):
        return self.publicKey

    def getDatabasePath(self):
        return self.databasePath

    def getPrivateKeyFilePath(self):
        return self.keyFilePath

    def getPluginItems(self):
        items = [[self.publicKeyItem.property.name, self.publicKeyItem.property.path, self.publicKeyItem()],
                 [self.groupListItem.property.name, self.groupListItem.property.path, self.groupListItem()],
                 [self.fromClientItem.property.name, self.fromClientItem.property.path, self.fromClientItem()]]
        return items


# ------------------------------------------
#    Webinterface class of the plugin
# ------------------------------------------


class WebInterface(SmartPluginWebIf):

    def __init__(self, webif_dir, plugin):
        """
        Initialization of instance of class WebInterface

        :param webif_dir: directory where the webinterface of the plugin resides
        :param plugin: instance of the plugin
        :type webif_dir: str
        :type plugin: object
        """
        self.logger = plugin.logger
        self.webif_dir = webif_dir
        self.plugin = plugin
        self.tplenv = self.init_template_environment()

    @cherrypy.expose
    def index(self, reload=None):
        """
        Build index.html for cherrypy

        Render the template and return the html file to be delivered to the browser

        :return: contents of the template after beeing rendered
        """
        tmpl = self.tplenv.get_template('index.html')

        # add values to be passed to the Jinja2 template eg: tmpl.render(p=self.plugin, interface=interface, ...)
        return tmpl.render(p=self.plugin)

    @cherrypy.expose
    def unsubscribeAll(self):
        self.plugin.unsubscribeAll()

# ------------------------------------------
#    Utils of the plugin
# ------------------------------------------
