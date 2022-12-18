#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2020-2021 Bernd Meiners                Bernd.Meiners@mail.de
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
from collections import OrderedDict
import xmltodict

logger = logging.getLogger("knxproject")

def int_to_lvl3_groupaddress(ga):
    """ converts an given integer into a string representing a three level group address """
    if ga <= 0 or ga > 32767:
        raise ValueError("Given Integer not in range for a valid group address")
    return "{0}/{1}/{2}".format((ga >> 11) & 0x1f, (ga >> 8) & 0x07, (ga) & 0xff)

def is_knxproject(filename):
    """
    check if given file is a valid knxproj file from ETS5
    """
    if not zipfile.is_zipfile(filename):
        return False

    knxproj = zipfile.ZipFile(filename, 'r')
    for file in knxproj.filelist:
        if file.filename == "knx_master.xml":
            break
    else:
        return False
    return True

def parse_projectfile(filename, password=None):
    """
    parse a Project file and return a dictionary with entries for every found group address
    { "0/1/5" : {'Id': 'P-0185-0_GA-8', 'Name': 'Lamellenstellung', 'Description': 'Wohnzimmer Markise', 'Comment' : '', 'DatapointType': 'DPST-5-1', 'Puid': '47'},
      "0/1/4" : {'Id': 'P-0185-0_GA-7', 'Name': 'Position', 'Description': 'Wohnzimmer Markise', 'Comment' : 'Nur 80% ausfahren', 'DatapointType': 'DPST-5-1', 'Puid': '45'}
    }
    so this dictionary can be walked through by ga as key
    """
    if is_knxproject(filename):
        return _parse_knxproject(filename, password)

    return _parse_esfproject(filename)

def _parse_esfproject(filename):
    """
    Parses the content from a esf file which is a result of an export from ETS
    
    File structure is like the following:
    ```
    Projectname
    main.middle.ga       \t    name        \t   type description        \t priority  \t    listen to
    ```
    example 
    ```
    central.lights.0/0/1            \t lights hallway                   \t EIS 1 'Switching' (1 Bit)            \t Low  \t
    central.dimming.1/2/40          \t main lights parents              \t EIS 2 'Dimming - control' (4 Bit)    \t Low  \t
    blinds.feedback height.3/3/100  \t kitchen sink blinds feedback pos \t Uncertain (1 Byte)                   \t Low  \t
    heating.set temperature.4/0/25  \t floor set temp feedback          \t Uncertain (2 Byte)                   \t Low  \t
    helper.time & date.8/0/0        \t time                             \t Uncertain (3 Byte)                   \t Low  \t
    helper.time & date.8/0/1        \t date                             \t Uncertain (3 Byte)                   \t Low  \t
    helper.counter.8/6/1            \t current inbound                  \t Uncertain (4 Byte)                   \t Low  \t
    ```

    Types are as follows:
    OPC-Typ     EIS-Format
    0           EIS 1 'Schalten' (1 Bit)
    1           EIS 8 'Skalieren – Steuerung' (2 Bit)
    2           Unbekannt
    3           EIS 2 'Dimmen – Steuerung' (4 Bit)
    4           Unbekannt
    5           Unbekannt
    6           Unbekannt
    7           Unbestimmt (1 Byte)
    8           Unbestimmt (2 Byte)
    9           Unbestimmt (3 Byte)
    10          Unbestimmt (4 Byte)
    11          Unbekannt
    12          Unbekannt
    13          Unbekannt
    14          EIS 15 'Zeichenkette' (14 Byte)
    15          Unbekannt
    """
    f = open(filename, 'r', encoding="iso-8859-15")
    projectname = f.readline()
    logger.debug("Start parsing Project '{0}' from file {1}".format(projectname, filename))
    GAs = {}

    for line in f.readlines():
        columns = line.split('\t')

        # now in the first column there is a compound object main.middle.ga
        # unfortunately we can not be sure that within main or middle there are no more  . or /
        # thus we need to find the rightmost . and separate the main and middle from the ga
        subcolumn = columns[0].split('.')
        if len(subcolumn) == 3 and len(columns) >= 4:
            ga = subcolumn[2]
            GAs[ga] = { "Id":"", 
                "HG" : subcolumn[0], 
                "MG" : subcolumn[1], 
                "Name": columns[1], 
                "Description": "", 
                "Comment": "", 
                "DatapointType": columns[2], 
                "Puid": "",
                "Priority": columns[3],
                "Listen": columns[4] }      # keep as string if present
        else:
            logger.debug("Codierungsfehler in {} gefunden --> ignoriert!".format(columns[0]))
    f.close()
    return GAs


def _parse_knxproject(filename, password=None):
    """
    Details can be found in ``KNX-XML Project-Schema-v17 - Description.pdf`` [1]
    As of ETS 5.x the zipfile contains one file named ``knx_master.xml`` which is not interesting for parsing the structure
    Then there are a couple of subdirectories named M-<1234> where <1234> is a placeholder for a manufacturer ID and
    also a subdirectory named P-<ABCD> which contains the relevant information, e.g.:
    P-03B3
        BinaryData    subdirectory with binary data for ETS
        ExtraData     subdirectory with extra data for ETS
        UserFiles     subdirectory with user supplied files
        project.xml   description of the contained (up to 16) projects as well as
                      further ProjectInformation like ``GroupAddressStyle`` which must be ``ThreeLevel`` here to work
        0.xml         a project description file that we need to examine

    A sample xml file for group addresses could contain e.g.
    ```xml
    <?xml version="1.0" encoding="utf-8"?>
    <KNX xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" CreatedBy="ETS5" ToolVersion="5.7.1093.38570" xmlns="http://knx.org/xml/project/20">
    <Project Id="P-0185">
        <Installations>
        <Installation Name="" BCUKey="4294967295" DefaultLine="P-0185-0_L-3" IPRoutingLatencyTolerance="2000">
            <Topology>...</Topology>
            <Locations>...</Locations>
            <GroupAddresses>
            <GroupRanges>
                <GroupRange Id="P-0185-0_GR-1" RangeStart="1" RangeEnd="2047" Name="Neue Hauptgruppe" Puid="26">
                    <GroupRange Id="P-0185-0_GR-2" RangeStart="1" RangeEnd="255" Name="Neue Mittelgruppe" Puid="27">
                        <GroupAddress Id="P-0185-0_GA-1" Address="1" Name="Schalten" Description="Schlafzimmer Eltern Lichtschalter" DatapointType="DPST-1-1" Puid="28" />
                        <GroupAddress Id="P-0185-0_GA-2" Address="2" Name="Status" Description="Schlafzimmer Eltern Lichtschalter" DatapointType="DPST-1-1" Puid="30" />
                    </GroupRange>
                    <GroupRange Id="P-0185-0_GR-3" RangeStart="256" RangeEnd="511" Name="Neue Mittelgruppe" Puid="36">
                        <GroupAddress Id="P-0185-0_GA-3" Address="256" Name="Bewegen" Description="Wohnzimmer Markise" DatapointType="DPST-1-8" Puid="37" />
                        <GroupAddress Id="P-0185-0_GA-4" Address="257" Name="Schritt/Stop" Description="Wohnzimmer Markise" DatapointType="DPST-1-7" Puid="39" />
                        <GroupAddress Id="P-0185-0_GA-5" Address="258" Name="Windalarm" Description="Wohnzimmer Markise" DatapointType="DPST-1-5" Puid="41" />
                        <GroupAddress Id="P-0185-0_GA-6" Address="259" Name="Regenalarm" Description="Wohnzimmer Markise" DatapointType="DPST-1-5" Puid="43" />
                        <GroupAddress Id="P-0185-0_GA-7" Address="260" Name="Position" Description="Wohnzimmer Markise" DatapointType="DPST-5-1" Puid="45" />
                        <GroupAddress Id="P-0185-0_GA-8" Address="261" Name="Lamellenstellung" Description="Wohnzimmer Markise" DatapointType="DPST-5-1" Puid="47" />
                    </GroupRange>
                </GroupRange>
            </GroupRanges>
            </GroupAddresses>
            <Trades> ... </Trades>
        </Installation>
        </Installations>
    </Project>
    </KNX>
    ```
    
    
    """
    # Zipfiles can have an empty password though it does not make sense except for confusion
    if password is None: 
        password = ''

    if isinstance(password, str):
        password = password.encode()

    xmldict = {}

    knxproj = zipfile.ZipFile(filename, 'r')

    # see which project files can be found
    subprojects = []
    for file in knxproj.filelist:
        logger.debug(f"File: {file}")
        if file.filename[0] != 'P':
            continue

        # According to Project Schema Description, page 41 future files can be named [0...16].xml
        if file.filename.split("/")[-1] != '0.xml':
            continue
        subprojects.append(file)
        logger.debug("Subfile '{}' found".format(file))

    zipped_subprojects = []
    for file in knxproj.filelist:
        print(file)
        if file.filename[0] != 'P':
            continue

        # According to Project Schema Description, page 41 future files can be named [0...16].xml
        if not file.filename.endswith('.zip'):
            continue
        zipped_subprojects.append(file)
        logger.debug("Zipped Subfile '{}' found".format(file))

    # currently only exactly one project file is allowed
    if len(subprojects) + len(zipped_subprojects) == 0:
        logger.error("No project file found to examine")
        return None

    if len(subprojects) + len(zipped_subprojects) > 1:
        logger.error("More than one project file found to examine, giving up!")
        return None

    xmlfile = None
    
    if (len(subprojects) == 0):
        zipped_subproject = knxproj.open(zipped_subprojects[0].filename)
        subproject = zipfile.ZipFile(zipped_subproject, 'r')
        logger.debug(f"subproject is {subproject}")
        for file in subproject.filelist:
            # According to Project Schema Description, page 41 future files can be named [0...16].xml
            if file.filename.split("/")[-1] != '0.xml':
                continue
            try:
                xmlfile = subproject.open(file.filename, pwd=password)
                xmldict = xmltodict.parse(xmlfile.read())
            except (RuntimeError, ValueError) as known_exception:
                logger.error(f"provided password does not work to open {file.filename}")
            except Exception as ex:
                logger.error(f"Error {ex}: could not open {file.filename} and read project file")
            break
    else:
        try:
            xmlfile = knxproj.open(subprojects[0].filename)
            xmldict = xmltodict.parse(xmlfile.read())
        except Exception as ex:
            logger.error(f"Error {ex}: could not open {subprojects[0].filename} and read project file")

    GAs = {}

    try:
        ga_dict = xmldict["KNX"]["Project"]["Installations"]["Installation"]["GroupAddresses"]["GroupRanges"]
        if ga_dict is None:
            logger.warning("No Group Ranges found. Please forward this info along with knxproj file to the author for problem search")
            return GAs

        top = ga_dict.get('GroupRange',None)
        if top is None: return GAs

        if isinstance(top, OrderedDict):
            # if there is only one child defined in xml, an ordered dict is
            # returned here instead of a list
            # so we need to convert it to a list
            main_ga = [top]
        else:
            main_ga = top

        for middle in main_ga:
            middle_dict = middle.get('GroupRange',None)
            if middle_dict is None: continue

            if isinstance( middle_dict, OrderedDict):
                # same as above
                middle_ga = [middle_dict]
            else:
                middle_ga = middle_dict

            for last in middle_ga:
                last_dict = last.get('GroupAddress', None)

                if last_dict is None: continue

                if isinstance( last_dict, OrderedDict):
                    # same as above
                    last_ga = [last_dict]
                else:
                    last_ga = last_dict

                for ga_dict in last_ga:
                        ga = ga_dict.get("@Address")
                        if ga:
                            ga = int_to_lvl3_groupaddress(int(ga))
                            GAs[ga] = {"Id": ga_dict.get("@Id"), 
                                "HG": middle.get("@Name"), 
                                "MG": last.get("@Name"), 
                                "Name": ga_dict.get("@Name"), 
                                "Description": ga_dict.get("@Description"), 
                                "Comment": ga_dict.get("@Comment"), 
                                "DatapointType": ga_dict.get("@DatapointType"), 
                                "Puid": ga_dict.get("@Puid")}
    except Exception as e: 
        print("Error {} occurred".format(e))
    return GAs
