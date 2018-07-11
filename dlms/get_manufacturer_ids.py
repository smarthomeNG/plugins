#!/usr/bin/env python3
# This Python file is able to visit
# http://dlms.com/organization/flagmanufacturesids/index.html
# download the list of manufacturer ids for smartmeter as html
# and parse out the ids together with the manufacturer
# The result will be stored locally as a manufacturer.yaml
# to serve as information database for the identification of smartmeters

import logging
import requests
from bs4 import BeautifulSoup
from ruamel.yaml import YAML

verbose = False
exportfile = 'manufacturer.yaml'

logging.getLogger().setLevel( logging.DEBUG )
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
# create formatter and add it to the handlers
if verbose:
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s  @ %(lineno)d')
else:
    formatter = logging.Formatter('%(message)s')
ch.setFormatter(formatter)
# add the handlers to the logger
logging.getLogger().addHandler(ch)
logger = logging.getLogger(__name__)


url = 'http://dlms.com/organization/flagmanufacturesids/index.html'
headers = {'User-agent': 'Mozilla/5.0'}


# result
r = {}
y = YAML()

try:
    logger.debug("Manufacturer IDs URL: {}".format(url))
    try:
        reque = requests.get(url, headers=headers)
    except ConnectionError as e:
        logger.debug('An error occurred fetching %s \n %s' % (url, e.reason) )
        raise
    
    soup = BeautifulSoup(reque.content.decode(reque.encoding), 'html.parser')

    tables = soup.find_all("table")
    
    for table in tables:
        try:
            rows = table.find_all('tr')
        except AttributeError as e:
            r += 'No table rows found, exiting'
            raise

        # Get data from rows """
        for row in rows:
            table_data = row.find_all('td')
            if table_data:
                id = table_data[0].get_text().strip()
                man = table_data[1].get_text().strip()
                r[id] = man

    with open(exportfile, 'w') as f:
        y.dump( r, f )

    logger.debug("{} distinct manufacturers were found and written to {}".format(len(r),exportfile))
    
except Exception as e:
    logger.debug("Error {} occurred".format(e))

