# Prowl

From https://www.prowlapp.com taken: 

> Prowl is a push notification client for iOS. Push to your
  iPhone, iPod touch, or iPad notifications from a Mac or Windows computer, or from a multitude of apps and services. Easily integrate the Prowl API into your applications.

## Requirements

This plugin has no requirements or dependencies, it just calls a web api.

## Configuration

### plugin.yaml

```
notify:
    class_name: Prowl
    class_path: plugins.prowl
    apikey: asdf1234asdf1234 # secret global key for prowl
    instance: Whatever # Instance name displayed in messages
```

#### Attributes
   * `apikey`: this attribute is optional. You could define a global **apikey** for the prowl service.
   * `instance`: this attribute is optional. If set it will be displayed in prowl messages.

## Functions

Because there is only one function you could access it directly by the object. With the above example it would look like this: ``sh.notify('Intrusion', 'Living room window broken!')``
This function takes several arguments:

 1. **event**: type of event.
 2. **description**: describes the event.
 3. **priority**: you could give a priority (0-2) to differentiate between events on your mobile device.
 4. **url**: This url would be linked to the notification.
 5. **apikey**: you could specify an individual apikey.
 6. application: describes the name of the application. By default it is SmartHome.

```python
# some examples
sh.notify('Intrusion', 'Living room window broken', 2, 'http://yourvisu.com/')
sh.notify('Tumbler', 'finished', apikey='qwerqwer')
```
