# homematic

## Requirements

Homematic Hardware Gateway

## Configuration

### plugin.conf

```
[homematic]
    class_name = Homematic
    class_path = plugins.homematic
    host = 192.168.50.250
    # port = 2001
    # cycle = 60
```

## items.conf
```
    [[deckenlicht_sofa]]
        name = Deckenlicht Sofa
        visu = yes
        type = bool
        hm_address = JEQ0017982
        hm_type = switch
```

### hm_type

Possible values

- for switches:

  - switch
  - 2ch_switch

- for raffstores:

  - pos
  - stop
  - move



