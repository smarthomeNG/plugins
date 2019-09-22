#!/usr/bin/env python
# parse weather data
# -*- coding: iso-8859-15 -*-

forecast = sh.wetter_com.forecast('CITYCODE')

d0 = sh.now().date()
d1 = (sh.now() + dateutil.relativedelta.relativedelta(days=1)).date()
d2 = (sh.now() + dateutil.relativedelta.relativedelta(days=2)).date()

items = { d0: sh.wetter.vorhersage.heute, d1: sh.wetter.vorhersage.morgen, d2: sh.wetter.vorhersage.uebermorgen}
try:
  for date in forecast:
    if date.date() in items:
        base = items[date.date()]
        if date.hour == 5 or date.hour == 6:
            frame = base.frueh
        elif date.hour == 11:
            frame = base.mittag
        elif date.hour == 23:
            frame = base.nacht
        else:  # hour == 18
            frame = base.spaet
        frame.temperatur.min(forecast[date][0])
        frame.temperatur.max(forecast[date][1])
        frame.text(forecast[date][2])
        frame.niederschlag(forecast[date][3])
        frame.wind.geschwindigkeit(forecast[date][4])
        frame.wind.richtung(forecast[date][5])
        frame.wind.richtung.text(forecast[date][6])
        frame.code(forecast[date][7])

except TypeError as e:
  logger.debug("Problems fetching wetter.com forecast.  TypeError: {}".format(e))

except AttributeError as e:
  logger.debug("Problems fetching wetter.com forecast.  AttributeError: {}".format(e))

except:
  e = sys.exc_info()[0]
  logger.debug("Problems fetching wetter.com forecast:  {}".format(e))

logger.debug(forecast)
