// ----- sonos.music_control ---------------------------------------------------------
$(document).delegate('span[data-widget="sonos.music_control"]', {
	'update': function (event, response) {
		event.stopPropagation();
		$(this).val(response);
		var action = $(this).attr('data-action');
		var active = false;
		if (response[0].toLowerCase().indexOf(action.toLowerCase()) >= 0){
			active = "true";
		}
		$(this).attr('data-val', response[1]);
		$(this).attr('data-active', active);
		$(this).trigger('draw', response);
	},
	'draw': function (event, response) {
		event.stopPropagation();
		var val_on = $(this).attr('data-val-on');
		var val_off = $(this).attr('data-val-off');
		var active = $(this).attr('data-active');

		if(active == "true") {
			if(val_on == $(this).attr('data-val')) {
				$(this).find('#' + this.id + '-inactive').hide();
				$(this).find('#' + this.id + '-active-on').show();
				$(this).find('#' + this.id + '-active-off').hide();
			}
			else {
				$(this).find('#' + this.id + '-inactive').hide();
				$(this).find('#' + this.id + '-active-on').hide();
				$(this).find('#' + this.id + '-active-off').show();
			}
		}
		else {
			$(this).find('#' + this.id + '-active-on').hide();
			$(this).find('#' + this.id + '-active-off').hide();
			$(this).find('#' + this.id + '-inactive').show();
		}
	},
	'click': function (event) {
		if ($(this).attr('data-active') == 'true') {
			io.write($(this).attr('data-send'), ($(this).val()[1] == $(this).attr('data-val-off') ? $(this).attr('data-val-on') : $(this).attr('data-val-off')) );
		}
	},
	'touchstart mousedown': function (event, response) {
		event.stopPropagation();
		if ($(this).attr('data-active') == 'true') {
			$(this).css({ transform: 'scale(.8)' });
		}
	},
	'touchend mouseup': function (event, response) {
		event.stopPropagation();
		$(this).css({ transform: 'scale(1)' });
	}
});

$(document).delegate('img[data-widget="sonos.cover"]', {
	'update': function (event, response) {
		event.stopPropagation();
		if (!response[0].trim()) {
		    $(this).attr('src', $(this).attr('data-cover'));
		}
		else {
			$(this).attr('src', response[0]);
		}
	}
});

$(document).delegate('div[data-widget="sonos.artist"]', {
	'update': function (event, response) {
		event.stopPropagation();
        $(this).html(response[0]);
	}
});

$(document).delegate('div[data-widget="sonos.title"]', {
	'update': function (event, response) {
		event.stopPropagation();
		if (!response[1].trim()) {
			$(this).html('No music');

		}
		else {
			$(this).html(response[0]);
		}
	}
});

$(document).delegate('div[data-widget="sonos.radio_station"]', {
	'update': function (event, response) {
		event.stopPropagation();
		if (!response[1].trim()) {
			$(this).html('No music');
		}
		else {
			$(this).html(response[0]);
		}
	}
});

$(document).delegate('div[data-widget="sonos.stream_content"]', {
	'update': function (event, response) {
		event.stopPropagation();
		$(this).html(response[0]);
	}
});

$(document).delegate('div[data-widget="sonos.album"]', {
	'update': function (event, response) {
		event.stopPropagation();
		$(this).html(response[0]);
	}
});

$(document).delegate('div[class="play"]', {
	'touchstart mousedown': function (event, response) {
		event.stopPropagation();
		$(this).css({ transform: 'scale(.8)' });
	},

	'touchend mouseup': function (event, response) {
		event.stopPropagation();
		$(this).css({ transform: 'scale(1)' });
	}
});

$(document).delegate('div[class="next"]', {

	'touchstart mousedown': function (event, response) {
		event.stopPropagation();
		$(this).css({ transform: 'scale(.8)' });
	},

	'touchend mouseup': function (event, response) {
		event.stopPropagation();
		$(this).css({ transform: 'scale(1)' });
	}
});


$(document).delegate('div[data-widget="sonos.streamtype"]', {
	'update': function (event, response) {
		event.stopPropagation();
		console.log(response[0]);
		var uid = $(this).attr('data-uid');
		var music = "#" + uid + "-div-music";
		var radio = "#" + uid + "-div-radio";
		if (response[0] === 'music') {
			$(music).show();
    		$(radio).hide();
		}
		else {
		    $(music).hide();
    		$(radio).show();
        }
	}
});

$(document).delegate('div[data-widget="sonos.playlists"]', {
	'update': function (event, response) {
        event.stopPropagation();
        var line = '';
        for (var i in response[0]) {
            var ret = '<a href="#" class="favorite">' + response[0][i] + '</a>';
            line += '<li data-icon="false">' + ret + '</li>';
        }
        $(this).find("ul").html(line).trigger('prepare').listview('refresh').trigger('redraw');
    },
	'click': function (event, response) {
	    var target = $( event.target );
        if ( target.is( "a" ) ) {
            if (target.hasClass( "favorite" )) {
                io.write($(this).attr('data-send'), target.html());
            }
        }
	}
});

