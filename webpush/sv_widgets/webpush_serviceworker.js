'use strict';

let openURLClick = "";

self.addEventListener('push', function (event) {
    console.log('[Service Worker] Push Received.');
    console.log(`[Service Worker] Push had this data: "${event.data.text()}"`);

    var data = JSON.parse(event.data.text());

    var title = 'Title';
    if (data.title !== '') {
        title = data.title;
    }

    var options = {
        body: data.body,
        requireInteraction:  data.requireInteraction
    };

    if (data.image !== '') {
        options.image = data.image;
    }

    if (data.icon !== '') {
        options.icon = data.icon;
    }

    if (data.badge !== '') {
        options.badge = data.badge;
    }

    if (data.silent !== '') {
        options.silent = data.silent;
    }

    if (data.vibrate  !== []) {
        options.vibrate  = data.vibrate ;
    }

    openURLClick = "";
    if (data.url !== '') {
        openURLClick = data.url;
    }

    event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener('notificationclick', function (event) {
    console.log('[Service Worker] Notification click received.');

    event.notification.close();

    if (openURLClick != "") {
        event.waitUntil(
            clients.openWindow(openURLClick)
        );
    }

});
