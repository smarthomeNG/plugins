#!/usr/bin/env python3
# snmp_1.py

# Abfrage von OIDs vie SNMP mit Scan der Items nach Attribut "oid".

from pysnmp.entity.rfc3413.oneliner import cmdgen
import time

logger.info("Logik SNMP: by :" + trigger['by'] )
#logger.info("Logik SNMP: source :" + trigger['source'] )
#logger.info("Logik SNMP: dest :" + trigger['dest'] )
#logger.info("Logik SNMP: value :" + trigger['value'] )

#SNMP_HOST = '192.168.2.9'
#SNMP_PORT = 161
#SNMP_COMMUNITY = 'meins'
 
for item in sh.find_items('oid'):    # findet alle Items die ein Attribut 'oid' besitzen
    oid = item.conf['oid']
    snmp_host = item.return_parent().conf['snmp_host']
    snmp_port = item.return_parent().conf['snmp_port']
    snmp_community = item.return_parent().conf['snmp_community']
    
    #logger.info(oid)
    #logger.info(snmp_host)
    #logger.info(snmp_port)
    #logger.info(snmp_community)
    
    cmdGen = cmdgen.CommandGenerator()
    
    errorIndication, errorStatus, errorIndex, varBinds = cmdGen.getCmd(
    cmdgen.CommunityData(snmp_community),
    cmdgen.UdpTransportTarget((snmp_host, snmp_port)), (oid)
    )
    # Check for errors and print out results
    if errorIndication:
        logger.info(errorIndication)
    else:
        if errorStatus:
            logger.info('%s at %s' % (
                errorStatus.prettyPrint(),
                errorIndex and varBinds[int(errorIndex)-1] or '?'
            )
        )
        else:
            for name, val in varBinds:
                #logger.info('%s = %s' % (name.prettyPrint(), val.prettyPrint()))
                item(str(val))