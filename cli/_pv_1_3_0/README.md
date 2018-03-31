# CLI v1.3.0 (up to shNG v1.3)

## Configuration

### plugin.yaml

```yaml
cli:
    class_name: CLI
    class_path: plugins.cli
    # ip = 127.0.0.1
    # port = 2323
    # update = false
    # hashed_password = 1245a9633edf47b7091f37c4d294b5be5a9936c81c5359b16d1c4833729965663f1943ef240959c53803fedef7ac19bd59c66ad7e7092d7dbf155ce45884607d
```

This plugin listens for a telnet connection.

``ip = `` used network interface, e.g. 127.0.0.1 (localhost, default) or listen on all network interfaces: 0.0.0.0
``port =`` used network port, default 2323
``update =`` restrict the access of the items to read only (false, default) or allows read/write access (true)
``hashed_password = `` password that needs to be entered on login. SHA-512 hashed. Value shown above is "very_secure_password"

The hashed_password can be obtained by using the backend's service page and the hash generator.

## Usage

Telnet to the configured IP adress and port.

Enter ``help`` for a list of available commands.

command | function
--- | ---
``cl [log]`` | clean (memory) log
``dl [logic]`` | dl logic: disables logic
``dump [item]`` | dump details about given item
``el [logic]`` | el logic: enables logic
``la`` | list all items (with values)
``ld [log]`` | log dump of (memory) log
``lo`` | list all logics and next execution time
``ls`` | list the first level items
``ls [item]`` | list item and every child item (with values)
``lt`` | list current thread names
``rl [logic]`` | reload logic
``rr [logic]`` | reload and run logic
``rt`` | return runtime
``si [task]`` | show details for given task
``sl`` | list all scheduler tasks by name
``st`` | list all scheduler tasks by execution time
``tr [logic]`` | trigger logic
``up`` | alias for update
``update [item] = [value]`` | update the specified item with the specified value
``quit`` | quit the session
``q`` | alias for quit

Plugins may append additional commands. They will be listed with the "help" command, too.

### Example:
``up office.light = On`` to update an item named _office.light_ to value _On_
