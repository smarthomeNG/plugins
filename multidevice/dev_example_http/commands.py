# commands for dev ex_tcp_cli
# these are example URLs used by me for testing at home. Feel free to modify

commands = {
    # shng_type str means return response as string (i.e. unaltered)
    'www': {
        'opcode': 'http://www.smarthomeng.de/',
        'read': True,
        'write': False,
        'shng_type': 'str',
        'dev_datatype': 'raw',
        'read_cmd': '$C'
    },
    # shng_type dict means return (string) response as dict
    'ac': {
        'opcode': 'http://192.168.2.234/dump1090-fa/data/aircraft.json',
        'read': True,
        'write': False,
        'shng_type': 'dict',
        'dev_datatype': 'raw',
        'read_cmd': '$C'
    },
    # dev_type shng_ws means create URL from opcode with parameters
    # shng_type dict means return (string) response as dict
    'knx': {
        'opcode': 'http://$P:host::$P:port:/ws/items/d.stat.knx.last_data',
        'read': True,
        'write': False,
        'shng_type': 'dict',
        'dev_datatype': 'webservices',
        'read_cmd': '$C'
    },
    # dev_type shng_ws means create URL from opcode with parameters
    # also able to write data with 'write_cmd' parameter syntax
    # shng_type dict means return (string) response as bool
    'lit': {
        'opcode': 'http://$P:host::$P:port:/ws/items/garage.licht',
        'read': True,
        'write': True,
        'shng_type': 'bool',
        'dev_datatype': 'webservices',
        'read_cmd': '$C',
        'write_cmd': '$C/$V',
        'read_data': {'dict': ['value']}
    }
}
