# AV Device

## Requirements
If you want to connect to your device via RS232 (recommended) you need to install:
Serial Python module

Install it with:
sudo pip3 install serial --upgrade

## Supported Hardware

Hopefully several different AV devices based on TCP or Serial RS232 connections
Tested with Pioneer (< 2016 models) and Denon AV receivers, Epson projector Oppo Bluray player

## Changelog

### v1.5.0
* Minor code re-write using smartplugin methods and logging
* added config file for Denon AVR1100
* fixed Denon example
* added Web Interface
* some bug fixes

### v1.3.6
* Major code re-write using multiple modules and classes, minimizing complexity
* Extended "translate" functionality with wildcards
* Implemented optional waiting time between multiple commands
* Improved Keep Command handling
* Several bug fixes and tests

### v1.3.5
* Implemented possibility to "translate" values
* Improved Wildcard handling
* Improved code
* Added Oppo support
* Improved response and queue handling

### v1.3.4
* Tested full Denon support
* Implemented Dependencies
* Implemented rudimentary Wildcard handling
* Implemented Initialization commands
* Improved Queue handling and CPU usage
* Bug fixes

### v1.3.3
* Added Denon support
* Added option to provide min-value in config file
* Improved response handling
* Implemented possibility to reload config files
* Improved verbose logging
* Bug fixes

### v1.3.2
* Added and tested full Denon support
