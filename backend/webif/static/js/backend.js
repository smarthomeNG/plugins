function switchLineWrapping(codeMirrorInstance) {
	codeMirrorInstance.setOption('lineWrapping', !codeMirrorInstance.getOption('lineWrapping'));
	if (codeMirrorInstance.getOption('lineWrapping')) {
		$('#linewrapping').addClass('active');
	} else {
		$('#linewrapping').removeClass('active');
	}
};

function triggerRestart() {
	/* get Request to start restart of shng */
	// ...
	var waitInMS = 2000;
	setTimeout(function() {
		checkBackendAvailability();
	}, waitInMS);
}

function checkBackendAvailability() {
	var reload = false;

	while (!reload) {
        $.ajax({
        	'url': "/backend/system.html",
			'async': false,
        	'type': "GET",
			'global': false,
        	'dataType': 'html',
			'success': function (data) {
       	         if (data.includes("SmartHomeNG")) {
                    reload = true;
                }
            }
		});
    }
    window.location.href = "/backend/system.html";
}

