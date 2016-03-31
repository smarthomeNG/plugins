    # hier die abgefangenen fehlermeldungen in den connections, die auf das fehleritem gemapped werden
    self._connErrors = ['Host is down', 'timed out', '[Errno 113] No route to host']


    def _fetch_url_v2(self, url, auth=None, username=None, password=None, timeout=2, method='GET', headers={}, body=None, errorItem=None):
        # im vergleich zu fetch_url habe ich einen error item, den ich setzen bei bekannten durch den user herbeigeführten connection fehlern
        # und die entsprechende fehlerabfragen, damit ich das log nicht voll schreibe
        plain = True
        if url.startswith('https'):
            plain = False
        lurl = url.split('/')
        host = lurl[2]
        purl = '/' + '/'.join(lurl[3:])
        path = host + purl
        if plain:
            conn = http.client.HTTPConnection(host, timeout=timeout)
        else:
            conn = http.client.HTTPSConnection(host, timeout=timeout)
        if auth == 'basic':
            headers['Authorization'] = self.basic_auth(username, password)
        elif auth == 'digest' and path in self.__paths:
            headers['Authorization'] = self.digest_auth(host, purl, {}, username, password, method)
        try:
            conn.request(method, purl, body, headers)
            resp = conn.getresponse()
        except Exception as e:
            # jetzt suchen wir nach bekannten, definierten fehlern
            if format(e) in self._connErrors:
                # diese fehler bekommen einen status, der in der visu oder sonst genutzt werden kann
                # wenn der item abgelegt ist, dann kann er auch gesetzt werden, wenn nicht schreiben wir halt ins log !
                if errorItem != None:
                    errorItem(True,'_request')
                else:
                    logger.warning('_request: error status set, not status item defined')
            else:
                logger.error('_request: problem in http.client exception : [{0}]'.format(e))
            if conn:
                conn.close()
                return None
        # ansonsten ist alles gut durchgelaufen, dann wird das item zurückgesetzt
        if errorItem != None:
            # wenn der item abgelegt ist, dann kann er auch rückgesetzt werden
            errorItem(False,'_request')
        # jetzt geht es an die auswertung der rueckmeldungen
        # rückmeldung 200 ist OK
        if resp.status == 200:
            content = resp.read()
        elif resp.status == 401 and auth == 'digest':
            content = resp.read()
            rheaders = self.parse_headers(resp.getheaders())
            headers['Authorization'] = self.digest_auth(host, purl, rheaders, username, password, method)
            conn.request(method, purl, body, headers)
            resp = conn.getresponse()
            content = resp.read()
        else:
            logger.warning("Problem fetching {0}: {1} {2}".format(url, resp.status, resp.reason))
            content = None
        conn.close()
        return content
