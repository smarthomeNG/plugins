function resizeCodeMirror(codeMirrorInstance, bottomSpace) {
    if (!codeMirrorInstance.getOption("fullScreen")) {
        var browserHeight = $( window ).height();
        offsetTop = $('.CodeMirror').offset().top;
        codeMirrorInstance.getScrollerElement().style.maxHeight = ((-1)*(offsetTop) - bottomSpace + browserHeight)+ 'px';
        codeMirrorInstance.refresh();
    }
}

function switchLineWrapping(codeMirrorInstance) {
	codeMirrorInstance.setOption('lineWrapping', !codeMirrorInstance.getOption('lineWrapping'));
	if (codeMirrorInstance.getOption('lineWrapping')) {
		$('#linewrapping').addClass('active');
	} else {
		$('#linewrapping').removeClass('active');
	}
};