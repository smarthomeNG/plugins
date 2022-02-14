#!/usr/bin/env python3

import re
import os

consts = []
with open("MD_Globals.py") as file:
    lines = file.readlines()

for line in lines:
    res = re.match(r'^([A-Z][A-Z_]+[A-Z1-3])\s+= ', line)
    if res:
        consts.append(res[1])

print(f'found {len(consts)} vars')

dir = os.fsencode(".")
print(dir)

for file in os.listdir(dir):

    file = str(file, 'utf-8')
    if file[-3:] == '.py':

        with open(file) as fx:
            f = fx.read()

        vars = []
        for var in consts:
            if var in f:
                vars.append(var)

        if vars:
            with open(file, 'w') as fx:
                fx.write(f'from MD_Globals import ({", ".join(sorted(vars))})\n')
                fx.write(f)
