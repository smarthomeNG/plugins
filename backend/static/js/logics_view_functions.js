
window.addEventListener("resize", resizeCodeMirror, false);

function resizeCodeMirror() {
    if (!logicsCodeMirror.getOption("fullScreen")) {
        var browserHeight = $( window ).height();
        offsetTop = $('.CodeMirror').offset().top;
        logicsCodeMirror.getScrollerElement().style.maxHeight = ((-1)*(offsetTop) - 15 + browserHeight)+ 'px';
        logicsCodeMirror.refresh();
    }
}

resizeCodeMirror();

var dict = [];
function getItemDictionary() {
    $.getJSON('items.json?mode=list', function(result) {
        for (i = 0; i < result.length; i++) {
            dict.push("sh."+result[i]);
        }
    });
}
getItemDictionary();

CodeMirror.registerHelper('hint', 'itemsHint', function(editor) {
    var cur = editor.getCursor(),
        curLine = editor.getLine(cur.line);
    var start = cur.ch,
        end = start;
    while (end < curLine.length && /[\w\.$]+/.test(curLine.charAt(end))) ++end;
    while (start && /[\w\.$]+/.test(curLine.charAt(start - 1))) --start;
    var curWord = start != end && curLine.slice(start, end);
    var regex = new RegExp('^' + curWord, 'i');
    return {
        list: (!curWord ? [] : dict.filter(function(item) {
            return item.match(regex);
        })).sort(),
        from: CodeMirror.Pos(cur.line, start),
        to: CodeMirror.Pos(cur.line, end)
    }
});

CodeMirror.commands.autocomplete_item = function(cm) {
    CodeMirror.showHint(cm, CodeMirror.hint.itemsHint);
};

function switchLineWrapping() {
	logicsCodeMirror.setOption('lineWrapping', !logicsCodeMirror.getOption('lineWrapping'));
	if (logicsCodeMirror.getOption('lineWrapping')) {
		$('#linewrapping').addClass('active');
	} else {
		$('#linewrapping').removeClass('active');
	}
}