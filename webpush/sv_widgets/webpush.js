if (!window.hasOwnProperty('webpushwidget')) {
    window.webpushwidget = null;
}

$.widget("sv.webpush", $.sv.widget, {
    initSelector: 'div[data-widget="webpush.config"]',

    applicationServerPublicKey: '',
    pushButton: null,
    swRegistration: null,

    // console logging
    verbose: false,

    options: {
		buttontext: 'Übernehmen',
	},

    _create: function () {
        this._super();
        this.widgetdiv = this.element[0];

        webpushwidget = this;

        this.pushButton = document.getElementById('webpush_config_submitbutton');
        this.registerWorker();
    },

    _update: function (response) {
        this.applicationServerPublicKey = response[1];

        var div = document.getElementById('webpush_config_checkboxdiv');
        div.innerHTML = "";
        var groupslist = JSON.parse(localStorage.getItem('webpush_groups'));
        if (groupslist === null){
            groupslist = []
        }

        for (const group of response[0]) {
            var checkboxdiv = document.createElement('div');
            checkboxdiv.id = 'checkboxdiv_' + group;
            checkboxdiv.className = "ui-checkbox";

            var label = document.createElement('label');
            label.className = "ui-btn ui-corner-all ui-btn-inherit ui-btn-icon-left";
            label.id = 'checkboxlabel_' + group;
            label.innerText = group;

            var checkbox = document.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.id = 'checkbox_' + group;
            checkbox.name = 'webpush_config_checkbox';
            checkbox.value = group;
            if (groupslist.includes(group)) {
                checkbox.checked = true;
            }

            label.appendChild(checkbox);
            checkboxdiv.appendChild(label);
            div.appendChild(checkboxdiv);
        }
    },

    urlB64ToUint8Array: function (base64String) {
        const padding = '='.repeat((4 - base64String.length % 4) % 4);
        const base64 = (base64String + padding)
            .replace(/\-/g, '+')
            .replace(/_/g, '/');

        const rawData = window.atob(base64);
        const outputArray = new Uint8Array(rawData.length);

        for (let i = 0; i < rawData.length; ++i) {
            outputArray[i] = rawData.charCodeAt(i);
        }
        return outputArray;
    },

    updateSubscription: function (subscription) {
        var sessionId = localStorage.getItem('webpush_sessionID');
        if (sessionId === null) {
            sessionId = "" + Date.now();
            localStorage.setItem('webpush_sessionID', sessionId);
        }

        var groupslist = [];
        var checkboxes = document.getElementsByName('webpush_config_checkbox');
        for (var i = 0; i < checkboxes.length; i++) {
                if (checkboxes[i].checked) {
                    groupslist.push(checkboxes[i].value);
                }
        }

        localStorage.setItem('webpush_groups', JSON.stringify(groupslist));

        var message = {
            sessionId: sessionId,
            groups: groupslist
        };

        if (groupslist === [] || subscription === '') {
            message.cmd = "unsubscribe";
            message.subscription = "";
        } else {
            message.cmd = "subscribe";
            message.subscription = subscription;
        }

        if (this.verbose)
            console.log(JSON.stringify(message));

        var items = this.options.item.explode();
        io.write(items[2], JSON.stringify(message));
    },

    unsubscribeUser: function () {
        this.swRegistration.pushManager.getSubscription()
            .then(function (subscription) {
                if (subscription) {
                    return subscription.unsubscribe();
                }
            })
            .catch(function (error) {
                console.log('Error unsubscribing', error);
            })
            .then(function () {
                if (webpushwidget.verbose)
                    console.log('User is unsubscribed.');
                webpushwidget.updateSubscription('');
            });
    },

    subscribeUser: function () {
        const applicationServerKey = this.urlB64ToUint8Array(this.applicationServerPublicKey);
        this.swRegistration.pushManager.subscribe({
            userVisibleOnly: true,
            applicationServerKey: applicationServerKey
        })
            .then(function (subscription) {
                if (webpushwidget.verbose)
                    console.log('User is subscribed.');
                webpushwidget.updateSubscription(subscription);
            })
            .catch(function (error) {
                console.error('Failed to subscribe the user: ', error);
            });
        return ""
    },

    initializeUI: function () {
        this.swRegistration.pushManager.getSubscription()
            .then(function (subscription) {
                if (Notification.permission === 'denied') {
                    webpushwidget.pushButton.textContent = 'Push Messaging Blocked';
                } else {
                    if (subscription === null) {
                        if (webpushwidget.verbose)
                            console.log('User is NOT subscribed.');
                    } else {
                        if (webpushwidget.verbose)
                            console.log('User IS subscribed.');
                    }

                    webpushwidget.pushButton.textContent = webpushwidget.options.buttontext;
                    webpushwidget.pushButton.addEventListener('click', function () {
                        var groupslist = [];
                        var checkboxes = document.getElementsByName('webpush_config_checkbox');
                        for (var i = 0; i < checkboxes.length; i++) {
                                if (checkboxes[i].checked) {
                                    groupslist.push(checkboxes[i].value);
                                }
                        }
                        if (groupslist.length > 0){
                            webpushwidget.subscribeUser();
                        } else{
                            webpushwidget.unsubscribeUser();
                        }
                    });
                }
            });
    },

    registerWorker: function () {
        if ('serviceWorker' in navigator) {
            if ('PushManager' in window) {
                if (webpushwidget.verbose)
                    console.log('Service Worker and Push are supported');

                // check where to search for the serviceworker file
                var url = 'dropins/shwidgets/webpush_serviceworker.js';
                var http = new XMLHttpRequest();
                http.open('HEAD', url, false);
                http.send();
                if (http.status == 404){
                    url = 'dropins/widgets/webpush_serviceworker.js';
                    http.open('HEAD', url, false);
                    http.send();
                    if (http.status == 404){
                        console.warn('Service Worker file not found in dropins/widgets/ or dropins/shwidgets/');
                        webpushwidget.pushButton.textContent = 'Could not find ServiceWorker';
                        return
                    }
                }
                navigator.serviceWorker.register(url)
                    .then(function (swReg) {
                        if (webpushwidget.verbose)
                            console.log('Service Worker is registered', swReg);
                        webpushwidget.swRegistration = swReg;
                        webpushwidget.initializeUI();
                    })
                    .catch(function (error) {
                        console.error('Service Worker Registration Error', error);
                        webpushwidget.pushButton.textContent = 'Push Not Supported';
                    });
            } else {
            console.warn('Push Manager not in window');
            webpushwidget.pushButton.textContent = 'Push Not Supported';
            }
        } else {
            console.warn('Service Worker not in navigator');
            webpushwidget.pushButton.textContent = 'Push Not Supported';
        }
    }
});