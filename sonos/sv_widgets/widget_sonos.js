
$.widget("sv.sonos_playlists", $.sv.widget, {
	initSelector: 'div[data-widget="sonos.playlists"]',

	options: {
		'data_item': $(this).attr('data-send')
	},

	_update: function (response) {
		var ul = this.element.children('ul:first').empty();
		var line = '';
		for (var i in response[0]) {
			var ret = '<a href="#" class="favorite">' + response[0][i] + '</a>';
			$('<li data-icon="false">' + ret + '</li>').appendTo(ul)
		}
		ul.trigger('prepare').listview('refresh').trigger('redraw');
	},
	_events: {
		'click > ul > li': function (event) {
				var playlist = $(event.target).html();
				var data_item = this.element.attr('data-send');
				io.write(data_item, playlist);
				$("#popup_sonos_playlists").popup('close');
		}
	}
});

$.widget("sv.sonos_cover", $.sv.widget, {
	initSelector: 'img[data-widget="sonos.cover"]',
	_update: function (response) {
		if (!response[0].trim()) {
			this.element.attr('src', this.element.attr('data-default'));
		}
		else {
			this.element.attr('src', response[0]);
		}
	}
});

$.widget("sv.sonos_title", $.sv.widget, {
	initSelector: 'div[data-widget="sonos.title"]',
	_update: function (response) {
		if (!response[1].trim()) {
			this.element.removeClass('title');
			this.element.addClass('nomusic');
			this.element.html('No music');
		}
		else {
			this.element.removeClass('nomusic')
			this.element.addClass('title')
			if (response[3].toLowerCase().indexOf('radio') == -1){
				this.element.html(response[0]);
			}
			else {
				this.element.html(response[2]);
			}
		}
	}
});

$.widget("sv.sonos_artist", $.sv.widget, {
	initSelector: 'div[data-widget="sonos.artist"]',
	_update: function (response) {
		if (response[2].toLowerCase().indexOf('radio') == -1){
			this.element.html(response[0]);
		}
		else {
			this.element.html(response[1]);
		}
	}
});

$.widget("sv.sonos_album", $.sv.widget, {
	initSelector: 'div[data-widget="sonos.album"]',
	_update: function (response) {
			this.element.html(response[0]);
	}
});


$.widget("sv.sonos_play", $.sv.widget, {

	initSelector: 'div[data-widget="sonos.play"]',

	_update: function (response) {
		if (response[1].toLowerCase().indexOf('play') == -1){
			this.element.addClass('inactive');
		}
		else {
			this.element.removeClass('inactive');
		}
	},

	_create: function() {
		this._super();

		this._on(this.element.find('a[data-widget="basic.stateswitch"]'), {
			'mousedown': function (event) {
				this.element.css({ '-webkit-transform': 'scale(.8)' });
			},

			'mouseup': function (event) {
				this.element.css({ '-webkit-transform': 'scale(1.4)' });
			}
		})
	}
});

$.widget("sv.sonos_previous", $.sv.widget, {

	initSelector: 'div[data-widget="sonos.previous"]',

	_update: function (response) {
		if (response[1].toLowerCase().indexOf('previous') == -1){
			this.element.addClass('inactive');
		}
		else {
			this.element.removeClass('inactive');
		}
	},

	_create: function() {
		this._super();

		this._on(this.element.find('a[data-widget="basic.stateswitch"]'), {
			'mousedown': function (event) {
				this.element.css({ '-webkit-transform': 'scale(.8)' });
			},

			'mouseup': function (event) {
				this.element.css({ '-webkit-transform': 'scale(1)' });
			}
		})
	}
});


$.widget("sv.sonos_next", $.sv.widget, {

	initSelector: 'div[data-widget="sonos.next"]',

	_update: function (response) {
		if (response[1].toLowerCase().indexOf('next') == -1){
			this.element.addClass('inactive');
		}
		else {
			this.element.removeClass('inactive');
		}
	},

	_create: function() {
		this._super();

		this._on(this.element.find('a[data-widget="basic.stateswitch"]'), {
			'mousedown': function (event) {
				this.element.css({ '-webkit-transform': 'scale(.8)' });
			},

			'mouseup': function (event) {
				this.element.css({ '-webkit-transform': 'scale(1)' });
			}
		})
	}
});
