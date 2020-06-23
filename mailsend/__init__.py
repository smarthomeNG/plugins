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
import smtplib
import email
import urllib
from email.mime.text import MIMEText
from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.image import MIMEImage

from lib.model.smartplugin import SmartPlugin
from bin.smarthome import VERSION


class SMTP(SmartPlugin):
    ALLOW_MULTIINSTANCE = True
    PLUGIN_VERSION = "1.4.0"

    def __init__(self, smarthome, host, mail_from, username='', password='', port=25, tls=False):
        self._sh = smarthome
        self._tls = self.to_bool(tls)
        self._host = host
        self._port = int(port)
        self._from = mail_from
        self._username = username
        self._password = password
        if '.'.join(VERSION.split('.', 2)[:2]) <= '1.5':
            self.logger = logging.getLogger(__name__)


    def send(self, to, sub, msg):
        self.__call__(to, sub, msg)

    def __call__(self, to, sub, msg):
        try:
            smtp = self._connect()
        except Exception as e:
            self.logger.warning("Could not connect to {0}: {1}".format(self._host, e))
            return
        try:
            msg = MIMEText(msg, 'plain', 'utf-8')
            msg['Subject'] = Header(sub, 'utf-8')
            msg['From'] = self._from
            msg['Date'] = email.utils.formatdate()
            msg['To'] = to
            msg['Message-ID'] = email.utils.make_msgid('SmartHomeNG')
            to = [x.strip() for x in to.split(',')]
            smtp.sendmail(self._from, to, msg.as_string())
        except Exception as e:
            self.logger.warning("Could not send message {} to {}: {}".format(sub, to, e))
        finally:
            try:
                smtp.quit()
                del (smtp)
            except:
                pass

    def extended(self, to, sub, msg, sender_name: str, img_list: list=[], attachments: list=[]):
        try:
            smtp = self._connect()
        except Exception as e:
            self.logger.warning("Could not connect to {0}: {1}".format(self._host, e))
            return
        try:
            sender_name = Header(sender_name, 'utf-8').encode()
            msg_root = MIMEMultipart('mixed')
            msg_root['Subject'] = Header(sub, 'utf-8')
            msg_root['From'] = email.utils.formataddr((sender_name, self._from))
            msg_root['Date'] = email.utils.formatdate(localtime=1)
            if not isinstance(to, list):
                to = [to]
            msg_root['To'] = email.utils.COMMASPACE.join(to)

            msg_root.preamble = 'This is a multi-part message in MIME format.'

            msg_related = MIMEMultipart('related')
            msg_root.attach(msg_related)

            msg_alternative = MIMEMultipart('alternative')
            msg_related.attach(msg_alternative)

            msg_text = MIMEText(msg.encode('utf-8'), 'plain', 'utf-8')
            msg_alternative.attach(msg_text)

            html = """
                <html>
                <head>
                <meta http-equiv="content-type" content="text/html;charset=utf-8" />
                </head>
                <body>
                <font face="verdana" size=2>{}<br/></font>
                <img src="cid:image0" border=0 />
                </body>
                </html>
                """.format(msg)  # template

            msg_html = MIMEText(html.encode('utf-8'), 'html', 'utf-8')
            msg_alternative.attach(msg_html)

            for i, img in enumerate(img_list):
                if img.startswith('http://'):
                    fp = urllib.request.urlopen(img)
                else:
                    fp = open(img, 'rb')
                msg_image = MIMEImage(fp.read())
                msg_image.add_header('Content-ID', '<image{}>'.format(i))
                msg_related.attach(msg_image)

            for attachment in attachments:
                fname = os.path.basename(attachment)

                if attachment.startswith('http://'):
                    f = urllib.request.urlopen(attachment)
                else:
                    f = open(attachment, 'rb')
                msg_attach = MIMEBase('application', 'octet-stream')
                msg_attach.set_payload(f.read())
                encoders.encode_base64(msg_attach)
                msg_attach.add_header('Content-Disposition', 'attachment',
                                      filename=(Header(fname, 'utf-8').encode()))
                msg_root.attach(msg_attach)

            smtp.send_message(msg_root)
        except Exception as e:
            self.logger.warning("Could not send message {} to {}: {}".format(sub, to, e))
        finally:
            try:
                smtp.quit()
                del(smtp)
            except:
                pass

    def _connect(self):
        smtp = smtplib.SMTP(self._host, self._port)
        if self._tls:
            smtp.starttls()
        if self._username != '':
            smtp.login(self._username, self._password)
        return smtp

    def run(self):
        self.alive = True

    def stop(self):
        self.alive = False

    def parse_item(self, item):
        pass

    def parse_logic(self, logic):
        pass

    def update_item(self, item, caller=None, source=None, dest=None):
        pass
