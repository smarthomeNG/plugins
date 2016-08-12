# CLI

Configuration
=============

plugin.conf
-----------
<pre>
[cli]
   class_name = CLI
   class_path = plugins.cli
#   ip = 127.0.0.1
#   port = 2323
#   update = false
   hashed_password = 1245a9633edf47b7091f37c4d294b5be5a9936c81c5359b16d1c4833729965663f1943ef240959c53803fedef7ac19bd59c66ad7e7092d7dbf155ce45884607d
</pre>

This plugin listens for a telnet connection. 
<code>ip = </code> used network interface, e.g. 127.0.0.1 (localhost, default) or listen on all network interfaces: 0.0.0.0
<code>port =</code> used network port, default 2323
<code>update =</code> restrict the access of the items to read only (false, default) or allows read/write access (true)
<code>hashed_password = </code> pasword that needs to be entered on login. SHA-512 hashed. Value shown above is "very_secure_password"
Usage
=====

Telnet to the configured IP adress and port. 
<code>help</code>list an set of available commands:
<pre>
cl: clean (memory) log
ld: log dump of (memory) logs
ls: list the first level items
ls item: list item and every child item (with values)
la: list all items (with values)
lo: list all logics and next execution time
lt: list current thread names
update item = value: update the specified item with the specified value
up: alias for update
dump item: dump details about given item
tr logic: trigger logic
rl logic: reload logic
rr logic: reload and run logic
quit: quit the session
q: alias for quit
</pre>

Example:
<code>up office.light = On</code> to update an item.
