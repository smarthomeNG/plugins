import logging
import codecs
import collections
import os

logger = logging.getLogger('logics.' + __name__)

logger.debug('Aufruf Check KNX')

"""
Requirements
------------

you need to adapt the path to your own ESF just below.
if you do not have one, it is a good idea to export it from ETS now
"""
esf = 'Smarthome.esf'

esf = os.path.join( sh.base_dir, 'var', esf)

if os.path.isfile(esf):
    # pyhon works with utf8 internally so we need to convert it, then chop the columns
    f = open(esf, 'r', encoding="iso-8859-15")
    projectname = f.readline()
    logger.debug("Start parsing Project '{0}' from file {1}".format(projectname, esf))

    ets_ga = {}

    for line in f.readlines():
        # main.middle.ga       \t    name        \t   type description        \t priority  \t    listen to
        # central.lights.0/0/1 \t lights hallway \t EIS 1 'Switching' (1 Bit) \t Low       \t
        columns = line.split('\t')

        # now in the first column there is a compound object main.middle.ga
        # unfortunately we can not be sure that within main or middle there are no more  . or /
        # thus we need to find the rightmost . and separate the main and middle from the ga
        subcolumn = columns[0].split('.')
        if len(subcolumn) == 3 and len(columns) >= 4:
            ga = subcolumn[2]
            ets_ga[ga] = {
                'main':subcolumn[0],
                'middle': subcolumn[1],
                'name': columns[1],
                'type': columns[2],
                'priority': columns[3],
                'listening': columns[4].split(' ')}
        else:
            logger.debug("Codierungsfehler in {} gefunden --> ignoriert!".format(columns[0]))

    f.close()

    logger.debug("Finished parsing Project '{0}' from file {1}, it contained {2} group addresses".format(projectname, esf, len(ets_ga)))

    outfile = os.path.splitext(esf)[0]+'.txt'

    nl = "\r\n"
    sep = "|"

    logger.debug("Preparing report and write to file {0}".format(outfile))

    out = "ESF aus ETS enthält {} Gruppenadressen".format(len(ets_ga))+nl+nl

    stats_ga = sh.knx.get_stats_ga()
    out += nl+nl+"Vom KNX wurden seit Start von SmartHomeNG bis jetzt {} Gruppenadressen gemeldet".format(len(stats_ga))+nl+nl
    od = collections.OrderedDict(sorted(stats_ga.items()))
    if len(od):
        out += "   GA    {0}read {0}write{0}response{0}name{1}".format(sep, nl)
        out += "--------------------------------------------------------------------------"+nl

    for ga in od:
        if ga in ets_ga:
            name = ets_ga.get(ga).get('name')
            if name:
                name = "{0}.{1}.{2}".format(ets_ga.get(ga).get('main'), ets_ga.get(ga).get('middle'), name )
            else:
                name = "--- Unbekannt in ETS ---"
        else:
            name = "--- Unbekannt in ETS ---"
        read = od[ga].get('read')
        read = read if read else ''
        write = od[ga].get('write')
        write = write if write else ''
        response = od[ga].get('response')
        response = response if response else ''
        out += "{2:>9}{0}{3:>5}{0}{4:>5}{0}{5:>8}{0}{6}{1}".format(sep, nl, ga, read, write, response, name)

    stats_pa = sh.knx.get_stats_pa()
    od = collections.OrderedDict(sorted(stats_pa.items()))
    if len(od):
        out += nl+nl
        out += "Es sind {0} physikalische Adressen gefunden worden".format(len(od))+nl+nl
        out += "   PA    {0}read {0}write{0}response{0}name{1}".format(sep, nl)
        out += "----------------------------------------------------------"+nl

    for pa in od:
        read = od[pa].get('read')
        read = read if read else ''
        write = od[pa].get('write')
        write = write if write else ''
        response = od[pa].get('response')
        response = response if response else ''
        out +="{2:>9}{0}{3:>5}{0}{4:>5}{0}{5:>8}{1}".format(sep, nl, pa, read, write, response)

    residual_ga = sh.knx.get_unsatisfied_cache_read_ga()
    if len(residual_ga)>0:
        out += nl+nl+"Folgende {0} Gruppenadressen wurden bisher NICHT aus dem Cache gelesen:".format(len(residual_ga))+nl
        out += "="*70+nl
        for ga in residual_ga:
            name = ""
            if ga in ets_ga:
                name = ets_ga.get(ga).get('name')
                if name:
                    name = " in ETS => {0}.{1}.{2}".format(ets_ga.get(ga).get('main'), ets_ga.get(ga).get('middle'), name )
                else:
                    name = " in ETS unbekannt"
            else:
                name = " in ETS unbekannt"
            out += "{0:>9}".format(ga) + name + nl


    # todo
    # iterate through all items to find those who are either
    # in ETS defined but not existent in SmartHomeNG
    # not defined in ETS but existent in SmartHomeNG
    # those defined in both should be cross checked for plausibility according to the data point types
    # eg. a 1-Bit in ETS should match a boolean in SmartHomeNG

    out += nl+nl+"Folgende Items sind mit Bezug zu KNX konfiguriert:"+nl
    out += "="*70+nl
    
    max_len_id = 0
    for item in sh.return_items():
        len_id = len(item.id())
        if len_id > max_len_id:
            max_len_id = len_id
    
    fmtStrg = "{0:<" + str(max_len_id) + "}"
    
    out += fmtStrg.format("item")
    for ct in ("type", "dpt", "GA", "bindtype"):
        out += sep + "{0:<10}".format(ct)
    out += sep + "ETS Name"
    out += nl
    out += "-"*(max_len_id+98) +nl
    
    item_ga = {}
    
    for item in sh.return_items():
        item_prefix = fmtStrg.format(item.id())
        item_prefix += "{1}{0:>10}".format(item.type(), sep)
            
        if "knx_dpt" in item.conf:
            item_prefix += "{1}{0:>10}".format(item.conf["knx_dpt"], sep)
            item_num = 0
            
            for ct in ("knx_listen", "knx_init", "knx_cache", "knx_send", "knx_status", "knx_reply", "knx_poll"):
                if ct in item.conf:
                    ele = item.conf[ct]
                    if isinstance(ele, list):
                        for ga in ele:
                            ets_name = ""
                            if ga in ets_ga:
                                ets_name = ets_ga.get(ga).get('name')
                                if ets_name:
                                    ets_name = " in ETS => {0}.{1}.{2}".format(ets_ga.get(ga).get('main'), ets_ga.get(ga).get('middle'), ets_name )
                                else:
                                    ets_name = " in ETS unbekannt"
                            else:
                                ets_name = " in ETS unbekannt"

                            to_add = {
                                'item_path':item.id(),
                                'item_type':item.type(),
                                'dpt':item.conf["knx_dpt"],
                                'bind_type':ct}

                            if ga not in item_ga:
                                item_ga[ga] = []
                            item_ga[ga].append(to_add)

                            out += "{2}{1}{0:>10}{1}{3:<10}{1}{4}".format(ga, sep, item_prefix, ct, ets_name) + nl
                            item_num += 1
                    else:
                        ga = ele

                        ets_name = ""
                        if ga in ets_ga:
                            ets_name = ets_ga.get(ga).get('name')
                            if ets_name:
                                ets_name = " in ETS => {0}.{1}.{2}".format(ets_ga.get(ga).get('main'), ets_ga.get(ga).get('middle'), ets_name )
                            else:
                                ets_name = " in ETS unbekannt"
                        else:
                            ets_name = " in ETS unbekannt"

                        to_add = {
                            'item_path':item.id(),
                            'item_type':item.type(),
                            'dpt':item.conf["knx_dpt"],
                            'bind_type':ct}

                        if ga not in item_ga:
                            item_ga[ga] = []
                        item_ga[ga].append(to_add)
                        
                        out += "{2}{1}{0:>10}{1}{3:<10}{1}{4}".format(ga, sep, item_prefix, ct, ets_name) + nl
                        item_num += 1
            
            if item_num == 0:
                out += "{2}{1}{0:>10}{1}{3:<10}{1}{4}".format(" ", sep, item_prefix, "- undef -", " ") + nl
                           

    out += nl+nl+"Folgende GAs sind in ETS konfiguriert:"+nl
    out += "="*70+nl
    
    max_len_ga = 0
    max_len_ga_tp = 0
    for ga in ets_ga:
        len_ga = len(ets_ga.get(ga).get('name'))
        len_ga_tp = len(ets_ga.get(ga).get('type'))
        if len_ga > max_len_ga:
            max_len_ga = len_ga
        if len_ga_tp > max_len_ga_tp:
            max_len_ga_tp = len_ga_tp
    
    fmt_string = "{0:>10}{1}{2:<"+str(max_len_ga)+"}{1}{3:<"+str(max_len_ga_tp)+"}{1}" 
    
    header = fmt_string.format("GA", sep, "ETS Name", "ETS Typ")    
    header += "{5:>6} {0}{3:>10}{0}{4:>10}{0}{1:>10}{0}{2}".format(sep, "BindType", "Item", "DPT", "Type", "#Items") + nl
    
    out += header
    out += "-" * len(header) + nl
    
    for ga in sorted(ets_ga):
        ga_prefix = fmt_string.format(ga, sep, ets_ga.get(ga).get('name'), ets_ga.get(ga).get('type'))
        
        if ga in item_ga:
            item_list = item_ga.get(ga)
            item_list_len = len(item_list)
            for it in item_list:
                out += ga_prefix + "{5:>6} {0}{3:>10}{0}{4:>10}{0}{1:>10}{0}{2}".format(sep, it.get('bind_type'), it.get('item_path'), it.get('dpt'), it.get('item_type'), item_list_len) + nl
        else:
            out += ga_prefix + "{5:>6} {0}{3:>10}{0}{4:>10}{0}{1:>10}{0}{2}".format(sep, "knx_?", "NICHT ALS ITEM ANGELEGT", "N/A", "?", 0) + nl

    try:
        f = open(outfile, 'w')
        f.write(out)
    except IOError as e:
        logger.error("Error '{0}' writing file {1}".format(e, outfile))
    finally:
        f.close()

logger.debug('Ende Check KNX')
