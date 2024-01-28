import json

def myconverter(o):
import datetime
if isinstance(o, datetime.datetime):
  return o.__str__()
data = sh.<your item here>.series('max','1d','now')
pretty = json.dumps(data, default = myconverter, indent = 2, separators=(',', ': '))
print(pretty)
