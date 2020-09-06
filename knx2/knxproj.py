#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2020 Bernd Meiners                     Bernd.Meiners@mail.de
#########################################################################
#  This file is part of SmartHomeNG.py.  
#  Visit:  https://github.com/smarthomeNG/
#          https://knx-user-forum.de/forum/supportforen/smarthome-py
#
#  SmartHomeNG.py is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  SmartHomeNG.py is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with SmartHomeNG.py. If not, see <http://www.gnu.org/licenses/>.
#########################################################################

import zipfile
import copy
import logging

from pathlib import Path
from lxml import etree

logger = logging.getLogger("knxproj")

#import dpts
"""
MAPPING = { \
    # xml          item type    knx datatype mapping in SmartHomeNG
    "DPST-1-1" : ( "bool", "1" )
    "DPST-13-10": "13.xxx",
    "DPST-14-56": "14.xxx",
    "DPST-225-1": None, # Type unknown in linknx
}

def Datatype(name):
    if name in DATATYPE.keys():
        return DATATYPE[name]
    n = name.split("-")
    if n[0] == "DPT":
        return "%s.xxx"%n[1]
    else:
        return "%i.%03i"%(int(n[1]),int(n[2]))
"""

"""
    '1': de1,
    '2': de2,
    '3': de3,
    '4002': de4002,
    '4.002': de4002,
    '5': de5,
    '5001': de5001,
    '5.001': de5001,
    '6': de6,
    '7': de7,
    '8': de8,
    '9': de9,
    '10': de10,
    '11': de11,
    '12': de12,
    '13': de13,
    '14': de14,
    '16000': de16000,
    '16': de16000,
    '16001': de16001,
    '16.001': de16001,
    '17': de17,
    '17001': de17001,
    '17.001': de17001,
    '18001': de18001,
    '18.001': de18001,
    '20': de20,
    '24': de24,
    '229': de229,
    '232': de232,
    '275.100' : de275100,
"""

def processRange(rng, lvl, name = []):
    names = copy.copy(name)
    new_names = rng.attrib['Name'].title().replace("/","").split()
    for i in names:
        for s in i:
            if s in new_names:
                new_names.remove(s)
    names.append(new_names)
    if "GroupRange" in rng.tag:
        for r in rng.getchildren():
            processRange(r,lvl + 1, names)
    elif "GroupAddress" in rng.tag:
        idname = "_".join([  "".join(s) for s in names])
        if "DatapointType" in rng.attrib.keys():
            datatype = Datatype(rng.attrib['DatapointType'])
        else:
            datatype = None
        addr = int(rng.attrib['Address'])
        addrs = []
        for mask in address_mask[lvl]:
            addrs.append("%i"%((addr & mask) >> ffs(mask)))
        gad = "/".join(addrs)
        objectlist.append( (idname, datatype, gad) )
    else:
        print("TYPE %s NOT SUPPORTED"%rng.tag)


def int_to_lvl3_groupaddress(ga):
    """ converts an given integer into a string representing a three level group address """
    if ga <= 0 or ga > 32767:
        raise ValueError("Given Integer not in range for a valid group address")
    return "{0}/{1}/{2}".format((ga >> 11) & 0x1f, (ga >> 8) & 0x07, (ga) & 0xff)

def strip_ns_prefix(tree):
    #xpath query for selecting all element nodes in namespace
    query = "descendant-or-self::*[namespace-uri()!='']"
    #for each element returned by the above xpath query...
    for element in tree.xpath(query):
        #replace element name with its local name
        element.tag = etree.QName(element).localname
    return tree

def parse_projectfile(filename):
    """
    parse a Project file and return a dictionary with entries for every found group address
    { "0/1/5" : {'Id': 'P-0185-0_GA-8', 'Name': 'Lamellenstellung', 'Description': 'Wohnzimmer Markise', 'Comment' : '', 'DatapointType': 'DPST-5-1', 'Puid': '47'},
      "0/1/4" : {'Id': 'P-0185-0_GA-7', 'Name': 'Position', 'Description': 'Wohnzimmer Markise', 'Comment' : 'Nur 80% ausfahren', 'DatapointType': 'DPST-5-1', 'Puid': '45'}
    }
    so this dictionary can be walked through by ga as key
    """
    if not zipfile.is_zipfile(filename):
        logger.error("this is not a valid *.knxproj file")
        return None

    knxproj = zipfile.ZipFile(filename, 'r')
    # Details can be found in ``KNX-XML Project-Schema-v17 - Description.pdf`` [1]
    # As of ETS 5.x the zipfile contains one file named ``knx_master.xml`` which is not interesting for parsing the structure
    # Then there are a couple of subdirectories named M-<1234> where <1234> is a placeholder for a manufacturer ID and
    # also a subdirectory named P-<ABCD> which contains the relevant information, e.g.:
    # P-03B3
    #   BinaryData    <subdirectory with binary data for ETS>
    #   ExtraData     <subdirectory with extra data for ETS>
    #   UserFiles     <subdirectory with user supplied files>
    #   project.xml   <description of the contained (up to 16) projects as well as
    #                   further ProjectInformation like ``GroupAddressStyle`` which must be ``ThreeLevel`` here to work
    #   0.xml         <a project description file that we need to examine

    # see which project files can be found
    subprojects = []
    for file in knxproj.filelist:
        if file.filename[0] != 'P':
            continue

        # ToDo: According to [1] page 41 future files can be named [0...16].xml
        # we stick with the basics here
        if file.filename.split("/")[-1] != '0.xml':
            continue
        subprojects.append(file)
        print(file)

    if len(subprojects) == 0:
        logger.error("No project file found to examine")
        return None

    if len(subprojects) > 1:
        logger.error("More than one project file found to examine, giving up!")
        return None

    # everything is fine, exactly one project is found
    # ToDo: ETS5 itself allows for different character sets such as windows native one but the xml files seem to have utf-8 only
    xmlfile = knxproj.open(subprojects[0].filename)
    xmldoc = etree.fromstring(xmlfile.read())
    xmlroot = strip_ns_prefix( xmldoc )
    
    #print(80*"*")
    #print(etree.tostring(xmlroot, pretty_print=True, encoding='unicode'))
    #print(80*"*")
    
    #level = 0
    GroupRanges = xmlroot.find("{*}Project/{*}Installations/{*}Installation/{*}GroupAddresses/{*}GroupRanges")

    #print(etree.tostring(GroupRanges, pretty_print=True, encoding='unicode'))
    #print(80*"*")

    #print(GroupRanges.tag,len(GroupRanges),GroupRanges.values)

    #for gr in list(GroupRanges):
    #    print(gr.tag)
    #print(80*"*")

    GAs = {}

    main_ga_elem = GroupRanges.findall('GroupRange')
    for level1 in main_ga_elem:
        #print(level1,level1.attrib["Id"])
        for level2 in level1:
            #print(".",level2,level2.attrib["Id"])
            for level3 in level2:
                ga = level3.attrib.get("Address")
                if ga:
                    ga = int_to_lvl3_groupaddress(int(ga))
                    GAs[ga] = { "Id":level3.attrib.get("Id"), "HG" : level1.attrib.get("Name"), "MG" : level2.attrib.get("Name"), "Name": level3.attrib.get("Name"), "Description":level3.attrib.get("Description"), "Comment":level3.attrib.get("Comment"), "DatapointType":level3.attrib.get("DatapointType"), "Puid":level3.attrib.get("Puid") }
                #print("..",level3,level3.attrib["Id"],ga)
                #print("..",level3,GAs[ga])

    return GAs

if __name__ == "__main__":

    parse_projectfile(Path("Demo.knxproj")

)