
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

    var charexp =  /[\w\.$]+/;
    while (end < curLine.length && charexp.test(curLine.charAt(end))) ++end;
    while (start && charexp.test(curLine.charAt(start - 1))) --start;
    var curWord = start != end && curLine.slice(start, end);
    if (curWord.length > 1) {
        curWord = curWord.trim();
    }
    var regex = new RegExp('^' + curWord, 'i');
    if (curWord.length >= 3) {
        return {
            list: (!curWord ? [] : dict.filter(function(item) {
                return item.match(regex);
            })).sort(),
            from: CodeMirror.Pos(cur.line, start),
            to: CodeMirror.Pos(cur.line, end)
        }
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

function switchRulers() {

	if (logicsCodeMirror.getOption('rulers').length == 0) {
		$('#rulers').addClass('active');
		logicsCodeMirror.setOption('rulers', rulers);
	} else {
		$('#rulers').removeClass('active');
		logicsCodeMirror.setOption('rulers', []);
	}
}