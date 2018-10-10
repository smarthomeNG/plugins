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
var watch_items_dict = [];
function getItemDictionary() {
    $.getJSON('items.json?mode=list', function(result) {
        for (i = 0; i < result.length; i++) {
            dict.push({ text: "sh."+result[i]+"()", displayText: "sh."+result[i]+"() | Item" });
            watch_items_dict.push({ text: result[i], displayText: result[i] });
            watch_items_dict.push({ text: result[i], displayText: "sh."+result[i] });
        }
    });
}
function getPluginDictionary() {
    $.getJSON('plugins.json', function(result) {
        for (i = 0; i < result.length; i++) {
            dict.push({ text: "sh."+result[i], displayText: "sh."+result[i]+" | Plugin"});
        }
    });
}
getItemDictionary();
getPluginDictionary();

function registerAutocompleteHelper(name, curDict) {
    CodeMirror.registerHelper('hint', name, function(editor) {
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
            var oCompletions = {
                list: (!curWord ? [] : curDict.filter(function (item) {
                    return item['displayText'].match(regex);
                })).sort(function(a, b){
                    var nameA=a.text.toLowerCase(), nameB=b.text.toLowerCase()
                    if (nameA < nameB) //sort string ascending
                        return -1
                    if (nameA > nameB)
                        return 1
                    return 0 //default return value (no sorting)
                }),
                from: CodeMirror.Pos(cur.line, start),
                to: CodeMirror.Pos(cur.line, end)
            };

            return oCompletions;
        }
    });
}

registerAutocompleteHelper('autocompleteHint', dict);
registerAutocompleteHelper('autocompleteWatchItemsHint', watch_items_dict);


CodeMirror.commands.autocomplete_shng = function(cm) {
    CodeMirror.showHint(cm, CodeMirror.hint.autocompleteHint);
};

CodeMirror.commands.autocomplete_shng_watch_items = function(cm) {
    CodeMirror.showHint(cm, CodeMirror.hint.autocompleteWatchItemsHint);
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
    $('#savereloadtrigger').removeClass('btn-shng-success');
    $('#savereload').removeClass('btn-shng-success');
    $('#save').removeClass('btn-shng-success');
    $('#savereloadtrigger').addClass('btn-shng-danger');
    $('#savereload').addClass('btn-shng-danger');
    $('#save').addClass('btn-shng-danger');
}

function markIdenticalContent() {
    $('#savereloadtrigger').removeClass('btn-shng-danger');
    $('#savereload').removeClass('btn-shng-danger');
    $('#save').removeClass('btn-shng-danger');
    $('#savereloadtrigger').addClass('btn-shng-success');
    $('#savereload').addClass('btn-shng-success');
    $('#save').addClass('btn-shng-success');
}
