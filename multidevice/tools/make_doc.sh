#!/bin/bash

TMPDIR="multidevice-doc-tmp"
if [ ! -f bin/smarthome.py ]; then

	echo please call from shng folder
	exit 1
fi

if [ ! -d plugins/multidevice ]; then

	echo can\'t find multidevice plugin folder
	exit 2
fi

mkdir $TMPDIR
mv -i plugins/multidevice/dev_* $TMPDIR
mv -i $TMPDIR/dev_example plugins/multidevice/

rm -Rf plugins/multidevice/doc/*

pdoc --force --html -o plugins/multidevice/doc plugins/multidevice

mv -i $TMPDIR/* plugins/multidevice/
rmdir $TMPDIR

