function switchLineWrapping(codeMirrorInstance) {
	codeMirrorInstance.setOption('lineWrapping', !codeMirrorInstance.getOption('lineWrapping'));
	if (codeMirrorInstance.getOption('lineWrapping')) {
		$('#linewrapping').addClass('active');
	} else {
		$('#linewrapping').removeClass('active');
	}
};