# Casambi 

#### Version 1.7.1

Gateway plugin for controlling and reading Casambi devices via the Casambi backend API.
Casambi devices are based on Bluetooth Low Energy (BLE) radio and integrated into many products such as
Occhio lights.

Official Casambi API documentation: 
https://developer.casambi.com/

## Change history

V1.7.1
Initial release

### Changes Since version 1.x.x

n/a

### Changes Since version 1.x.w

- Added that feature


## Requirements

The plugin needs a valid Casambi API key which can be obtained from Casambi under: 
support@casambi.com

### Needed software

None

### Supported Hardware

According to the Casambi concept, a mobile device (cell phone or tablet) is used as hardware gateway between local 
BLE network and Casambi backend.  

## Configuration

### plugin.yaml

Please refer to the documentation generated from plugin.yaml metadata.


### items.yaml

Please refer to the documentation generated from plugin.yaml metadata.


### logic.yaml
Please refer to the documentation generated from plugin.yaml metadata.


## Methods
Please refer to the documentation generated from plugin.yaml metadata.


## Examples
Example for dimmer (Occhio Sento) with dimming and additional up/down fading feature.
Item tree:

    readinglight:
        casambi_id: 2
        enforce_updates: True
        
        light:
            type: bool
            casambi_rx_key: ON
            casambi_tx_key: ON
            visu_acl: rw
            enforce_updates: True

            level:
                type: num
                value: 0
                casambi_rx_key: DIMMER
                casambi_tx_key: DIMMER
                visu_acl: rw
                enforce_updates: True

            vertical:
                type: num
                value: 0
                casambi_rx_key: VERTICAL
                casambi_tx_key: VERTICAL
                visu_acl: rw
                enforce_updates: True



