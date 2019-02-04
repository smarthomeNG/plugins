# iCal

## Functions
Because there is only one function, you could access it directly by the object.
With the above `plugin.yaml` it would look like this: `events = sh.ical('http://cal.server/my.ical')`.

Example logic:
```python
today = sh.now().date()

holidays = sh.ical('/usr/local/smarthome/holidays.ical')
if today in holidays:
    logger.info('yeah')
else:
    logger.info('naah')

events = sh.ical('http://cal.server/events.ical')
for day in events:
    logger.info("Date: {0}".format(day))
    for event in events[day]:
        start = event['Start']
        summary = event['Summary']
        cal_class = event['Class']
        logger.info("Time: {0} {1}".format(start, summary))
        if 'testword' in str(summary).lower():
            logger.info('calendar entry with testword found')
            if start.date() == tomorrow:
                logger.info('Textword calendar entry starts tommorrow')
        if 'private' in str(cal_class).lower():
            logger.info('Private calendar entry found.')
```
