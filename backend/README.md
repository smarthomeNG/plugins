# Backend GUI

This plugin delivers information about the current SmarthomeNG installation. Right now it serves as a support tool for helping other users with an installation that does not run properly. Some highlights:

* a list of installed python modules is shown versus the available versions from PyPI
* a list of items and their attributes is shown
* a list of logics and their next execution time
* a list of current schedulers and their next execution time
* direct download of sqlite database (if plugin is used) and smarthome.log
* some information about frequently used daemons like knxd is included

There is however no protection for unauthorized access or use of the plugin so be careful when enabling it with your network.

The plugin might be used standalone as well.

It is still in early development so please give feedback to the community.

# Requirements
This plugin requires Python >= 3.4 as well as the libs cherrypy and jinja2. You can install them with:
<pre>
(sudo apt-get install python-cherrypy)
sudo pip install cherrypy
(sudo apt-get install python-jinja2)
sudo pip install jinja2
</pre>
And please pay attention that the libs are installed for Python3 and not an older Python 2.7 that is probably installed on your system.

.

To support visualization, the visu_websocket plugin has to be used. It has to be PLUGIN_VERSION >= "1.1.2".


# Configuration

## plugin.conf
<pre>
[BackendServer]
   class_name = BackendServer
   class_path = plugins.backend
   #ip = xxx.xxx.xxx.xxx
   #port = xxxx
</pre>

### Attributes
  * `ip`: IP address to start the backend server (default localhost).
  * `port`: Port of the backend server (default 8080).
