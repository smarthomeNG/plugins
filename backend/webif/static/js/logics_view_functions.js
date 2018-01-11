$('#help').click(function(e) {
  $('#help_text').toggle();
  resizeCodeMirror()
});
$('#linewrapping').click(function(e) {
    switchLineWrapping(logicsCodeMirror)
});
$('#rulers').click(function(e) {
    switchRulers();
});

window.addEventListener("resize", function(){resizeCodeMirror(logicsCodeMirror, 15)}, false);
resizeCodeMirror(logicsCodeMirror, 15);

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

function switchRulers() {

	if (logicsCodeMirror.getOption('rulers').length == 0) {
		$('#rulers').addClass('active');
		logicsCodeMirror.setOption('rulers', rulers);
	} else {
		$('#rulers').removeClass('active');
		logicsCodeMirror.setOption('rulers', []);
	}
};

function checkChangedContent() {
    if ($('#original_content').val() != logicsCodeMirror.getValue() || ($('#original_cycle').val() != $('#cycle').val()) || ($('#original_crontab').val() != $('#crontab').val()) || ($('#original_watch').val() != $('#watch').val())) {
        return true;
    } else {
        return false;
    }
};

function markChangedContent() {
    $('#savereloadtrigger').removeClass('btn-success');
    $('#savereload').removeClass('btn-success');
    $('#save').removeClass('btn-success');
    $('#savereloadtrigger').addClass('btn-danger');
    $('#savereload').addClass('btn-danger');
    $('#save').addClass('btn-danger');
}

function markIdenticalContent() {
    $('#savereloadtrigger').removeClass('btn-danger');
    $('#savereload').removeClass('btn-danger');
    $('#save').removeClass('btn-danger');
    $('#savereloadtrigger').addClass('btn-success');
    $('#savereload').addClass('btn-success');
    $('#save').addClass('btn-success');
}