function resizeCodeMirror(codeMirrorInstance, bottomSpace) {
    if (!codeMirrorInstance.getOption("fullScreen")) {
        var browserHeight = $( window ).height();
        offsetTop = $('.CodeMirror').offset().top;
        codeMirrorInstance.getScrollerElement().style.maxHeight = ((-1)*(offsetTop) - bottomSpace + browserHeight)+ 'px';
        codeMirrorInstance.refresh();
    }
}
