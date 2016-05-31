# Backend GUI

Plugin in development...

# Requirements
This plugin requires lib cherrypy and lib jinja2. You can install this lib with:
<pre>
(sudo apt-get install python-cherrypy)
sudo pip-3.2 install cherrypy
(sudo apt-get install python-jinja2)
sudo pip-3.2 install jinja2
</pre>

# Configuration

## plugin.conf
<pre>
[BackendServer]
   class_name = BackendServer
   class_path = plugins.backend
   sh_dir = /volume1/python/smarthome
   #ip = xxx.xxx.xxx.xxx
   #port = xxxx
</pre>

### Attributes
  * `ip`: IP address to start the backend server (default localhost).
  * `port`: Port of the backend server (default 8080).
  * `sh_dir`: Directory, where smarthomeNG is installed to.