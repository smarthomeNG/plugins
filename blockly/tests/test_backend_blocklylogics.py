# -*- coding: utf-8 -*-
from tests import common
import cherrypy
from bs4 import BeautifulSoup

import lib.item

from plugins.backend import WebInterface as Root
from plugins.backend.tests.cptestcase import BaseCherryPyTestCase
from tests.mock.core import MockSmartHome


def setUpModule():
#    bs = MockBackendServer()
#    sh = bs._sh
#    cherrypy.tree.mount(Root(backendserver=bs,developer_mode=True), '/')
#    cherrypy.engine.start()
    pass
setup_module = setUpModule


def tearDownModule():
#    cherrypy.engine.exit()
    pass
teardown_module = tearDownModule


class TestCherryPyApp(BaseCherryPyTestCase):
    def test_blockly(self):
        pass
        # dummy, because tests are from the tightly coupled 1. try do integrate blockly 
        # (before it became a seperate plugin)
        
#    def test_backendIntegration(self):
#        response = self.request('index')
#        self.assertEqual(response.output_status, b'200 OK')
#        body = BeautifulSoup(response.body[0])
#        self.assertEqual( str(body.find("a", href="logics.html"))[:2], '<a' )
        #self.assertEqual( str(body.find("a", href="logics_blockly.html"))[:2], '<a' )

#     def test_logics_blockly_html(self):
#         response = self.request('logics_blockly_html')
#         self.assertEqual(response.output_status, b'200 OK')
#         resp_body = str(response.body[0],'utf-8')
#         self.assertRegex(resp_body, 'xml id="toolbox"')
#         self.assertRegex(resp_body, 'div id="content_blocks"')
#         self.assertRegex(resp_body, '<category name="Trigger">')
#         # self.assertEqual(response.body, ['hello world'])

#     def test_DynToolbox(self):
#         response = self.request('logics_blockly_html')
#         #resp_body = str(response.body[0],'utf-8')
#         bs_body = BeautifulSoup(response.body[0])
#         #items = bs_body.find("category", name="SmartHome Items")
#         shItemsCat = bs_body.xml.find_all(attrs={'name': 'SmartHome Items'})[0]
#         # print(shItemsCat)
#         # print("categories: {}".format(len(list(shItemsCat.find_all("category")))) )
#         # print("    blocks: {}".format(len(shItemsCat.find_all("block", type="sh_item_obj") )) )
#         self.assertEqual(len(list(shItemsCat.find_all("block", type="sh_item_obj") )), 9 )
#         self.assertEqual(len(list(shItemsCat.find_all("category") )), 6 )

#     def test_logics_blockly_load(self):
#         response = self.request('logics_blockly_load')
#         self.assertEqual(response.output_status, b'200 OK')
#         resp_xml = str(response.body[0],'utf-8')
#         #print(resp_xml)
#         self.assertRegex(resp_xml, '<field name="N">Unit Test</field>')
#         self.assertRegex(resp_xml, '<field name="P">testen.unit.test</field>')
#         self.assertRegex(resp_xml, '<field name="T">bool</field>')



    # def test_logics_blockly_load(self):
    #     with open(fn_py, 'w') as fpy:
    #         with open(fn_xml, 'w') as fxml:
    #             fpy.write(py)
    #             fxml.write(xml)

    # def test_echo(self):
    #     response = self.request('/echo', msg="hey there")
    #     self.assertEqual(response.output_status, '200 OK')
    #     self.assertEqual(response.body, ["hey there"])
    #
    #     response = self.request('/echo', method='POST', msg="back from the future")
    #     self.assertEqual(response.output_status, '200 OK')
    #     self.assertEqual(response.body, ["back from the future"])
    #


class MockBackendServer():
    _sh = MockSmartHome()

    def __init__(self):
        self._sh.with_items_from(common.BASE + "/tests/resources/blockly_items.conf")

        # HACK: Make tests work! Backend accesses private field _logic_dir
        # directly instead of using a method (the field was remove in the
        # meantime). Setting this just to make it work again.
        self._sh._logic_dir = common.BASE + "/tests/resources/"


if __name__ == '__main__':
    import unittest
    unittest.main()
