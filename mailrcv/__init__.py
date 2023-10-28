#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2012-2013 Marcus Popp                         marcus@popp.mx
#########################################################################
#  This file is part of SmartHomeNG.    https://github.com/smarthomeNG//
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

import logging
import imaplib
import email

from lib.model.smartplugin import SmartPlugin
from bin.smarthome import VERSION


class IMAP(SmartPlugin):
    ALLOW_MULTIINSTANCE = True
    PLUGIN_VERSION = "1.4.2"

    def __init__(self, sh, *args, **kwargs):
        super().__init__() 
        self._host = self.get_parameter_value('host')
        self._port = self.get_parameter_value('port')
        self._username = self.get_parameter_value('username')
        self._password = self.get_parameter_value('password')
        self.cycle = self.get_parameter_value('cycle')
        self._tls = self.get_parameter_value('tls')
        self._trashfolder = self.get_parameter_value('trashfolder')
        self._mail_sub = {}
        self._mail_to = {}
        self._mail = None

        if '.'.join(VERSION.split('.', 2)[:2]) <= '1.5':
            self.logger = logging.getLogger(__name__)

    def _connect(self):
        if self._tls:
            if self._port is not None:
                imap = imaplib.IMAP4_SSL(self._host, self._port)
            else:
                imap = imaplib.IMAP4_SSL(self._host)
        else:
            if self._port is not None:
                imap = imaplib.IMAP4(self._host, self._port)
            else:
                imap = imaplib.IMAP4(self._host)
        imap.login(self._username, self._password)
        return imap

    def _cycle(self):
        try:
            imap = self._connect()
        except Exception as e:
            self.logger.warning("Could not connect to {0}: {1}".format(self._host, e))
            return
        try:
            rsp, data = imap.select()
        except Exception as e:
            self.logger.warning("Problem getting mail on host {0}: {1}".format(self._host, e))
            return
        if rsp != 'OK':
            self.logger.warning("IMAP: Could not select mailbox")
            try:
                imap.close()
                imap.logout()
            except Exception:
                pass
            return
        rsp, data = imap.uid('search', None, "ALL")
        if rsp != 'OK':
            self.logger.warning("IMAP: Could not search mailbox")
            try:
                imap.close()
                imap.logout()
            except Exception:
                pass
            return
        uids = data[0].split()
        for uid in uids:
            if not self.alive:
                break
            mail = {}
            try:
                rsp, data = imap.uid('fetch', uid, '(RFC822)')
                if rsp != 'OK':
                    self.logger.warning("IMAP: Could not fetch mail")
                    continue
                try:
                    mail = email.message_from_bytes(data[0][1])
                except Exception as e:
                    if len(data) < 2:
                        self.logger.warning("IMAP: problem getting message {} from data: "
                                            "data-list has length {} and data[0] = '{}' "
                                            "Error: {}".format(uid, len(data), data[0], e))
                    if len(data) > 1:
                        self.logger.warning("data[1] = '{}'. Error: {}".format(data[1], e))
                    break
                # If a (non standard-conforming) mail without content-transfer-encoding is received, decoding the mail content fails.
                # In this case we set the encoding to the official standard, which should be a good guess.
                if 'content-transfer-encoding' not in mail:
                    mail['content-transfer-encoding'] = '7BIT'
                to = email.utils.parseaddr(mail['To'])[1]
                fo = email.utils.parseaddr(mail['From'])[1]
                if mail['Subject'] is None:
                    subject = 'no subject'
                else:
                    subject, encoding = email.header.decode_header(mail['Subject'])[0]
                    if encoding is not None:
                        subject = subject.decode(encoding)
            except Exception as e:
                self.logger.error("IMAP: problem parsing message {} with subject {}: {}".format(uid, mail.get('Subject'), e))
                # self.logger.warning("data = '{}', mail = '{}'".format(data, mail))
                continue
            if subject in self._mail_sub:
                logic = self._mail_sub[subject]
            elif to in self._mail_to:
                logic = self._mail_to[to]
            elif self._mail:
                logic = self._mail
            else:
                logic = None
            if logic is not None:
                logic.trigger('IMAP', fo, mail, dest=to)
                if self._host.lower() == 'imap.gmail.com':
                    typ, data = imap.uid('store', uid, '+X-GM-LABELS', '\\Trash')
                    if typ == 'OK':
                        self.logger.debug("Moving mail to trash. {0} => {1}: {2}".format(fo, to, subject))
                    else:
                        self.logger.warning("Could not move mail to trash. {0} => {1}: {2}".format(fo, to, subject))
                else:
                    rsp, data = imap.uid('copy', uid, self._trashfolder)
                    if rsp == 'OK':
                        typ, data = imap.uid('store', uid, '+FLAGS', '(\Deleted)')
                        self.logger.debug("Moving mail to trash. {0} => {1}: {2}".format(fo, to, subject))
                    else:
                        self.logger.warning("Could not move mail to trash. {0} => {1}: {2}".format(fo, to, subject))
                        self.logger.info("Consider setting the trashfolder option to the name of your trash mailbox.")
                        mailboxes = []
                        for mb in imap.list()[1]:
                            if mb is not None:
                                mailboxes.append(mb.decode("utf-8"))
                        if mailboxes:
                            self.logger.info("Available mailboxes are: {}".format(mailboxes))
                        else:
                            self.logger.info("No trash mailboxes available")
            else:
                self.logger.info("Ignoring mail. {0} => {1}: {2}".format(fo, to, subject))
        try:
            imap.close()
            imap.logout()
        except Exception:
            pass

    def run(self):
        self.alive = True
        self.scheduler_add('IMAP', self._cycle, cycle=self.cycle)

    def stop(self):
        self.alive = False

    def parse_item(self, item):
        pass

    def parse_logic(self, logic):
        if 'mail_subject' in logic.conf:
            self._mail_sub[logic.conf['mail_subject']] = logic
        if 'mail_to' in logic.conf:
            self._mail_to[logic.conf['mail_to']] = logic
        if 'mail' in logic.conf:
            self._mail = logic

    def update_item(self, item, caller=None, source=None, dest=None):
        pass
