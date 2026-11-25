/**
 * -----------------------------------------------------------------------------
 * smartVISU widgets of the SmartHomeNG plugin deebot
 *
 * deebot.panel  state, control, settings, wear parts and room selection of a vacuum
 * deebot.map    map of the vacuum
 *
 * Both are configured through the macros in deebot.html and expect the items of the
 * item struct deebot.all below a common base item.
 * -----------------------------------------------------------------------------
 */

var DEEBOT_STATE_LABELS = {
    idle: 'bereit',
    cleaning: 'reinigt',
    returning: 'fährt zur Station',
    docked: 'in der Station',
    error: 'Fehler',
    paused: 'pausiert'
};

/** Items the panel listens to, in the order of the data-item attribute written by the macro (wear parts follow). */
var DEEBOT_PANEL_FIELDS = ['state', 'active', 'battery', 'available', 'error_code', 'error_text', 'station_state',
    'clean_area', 'clean_time', 'rooms'];

/** Items the panel writes to; the macro passes their paths as data-item-<name with - for _>. */
var DEEBOT_PANEL_TARGETS = ['cmd_start', 'cmd_pause', 'cmd_resume', 'cmd_stop', 'cmd_dock', 'cmd_locate',
    'cmd_clean_rooms'];

/** Button that starts, pauses or resumes the cleaning, depending on the state of the vacuum. */
function deebotPrimaryAction(state) {
    if (state === 'cleaning' || state === 'returning') {
        return {cmd: 'cmd_pause', label: '⏸', title: 'Pause'};
    }
    if (state === 'paused') {
        return {cmd: 'cmd_resume', label: '▶', title: 'Fortsetzen'};
    }
    return {cmd: 'cmd_start', label: '▶', title: 'Start'};
}

function deebotStateLabel(state, available) {
    if (available === false) {
        return 'nicht erreichbar';
    }
    return DEEBOT_STATE_LABELS[state] || state || '-';
}

/** CSS class of the state text, empty for the states that need no highlight. */
function deebotStateClass(state, available) {
    if (available === false) {
        return 'deebot-state-unavailable';
    }
    return ['cleaning', 'returning', 'error', 'paused'].indexOf(state) >= 0 ? 'deebot-state-' + state : '';
}

/** Rooms as [{id, name, preselect}] ordered by id, whatever shape (array or JSON text) the item value arrives in. */
function deebotRooms(value) {
    if (typeof value === 'string') {
        try {
            value = JSON.parse(value);
        } catch (e) {
            return [];
        }
    }
    if (!Array.isArray(value)) {
        return [];
    }
    return value.filter(function (room) {
        return room && room.id !== undefined;
    }).map(function (room) {
        return {id: Number(room.id), name: String(room.name || room.id), preselect: Boolean(room.preselect)};
    }).sort(function (a, b) {
        return a.id - b.id;
    });
}

/** Duration in seconds as whole minutes, e.g. 5280 -> '88 min'. */
function deebotMinutes(seconds) {
    return Math.round(Number(seconds) / 60) + ' min';
}

/** Room names for display; rooms sharing a name (e.g. several unnamed ones) get their id appended. */
function deebotRoomLabels(rooms) {
    var counts = {};
    rooms.forEach(function (room) {
        counts[room.name] = (counts[room.name] || 0) + 1;
    });
    return rooms.map(function (room) {
        return counts[room.name] > 1 ? room.name + ' (' + room.id + ')' : room.name;
    });
}

/** Remaining life in percent limited to 0..100, null if the value is no number. */
function deebotPercent(value) {
    var number = parseFloat(value);
    if (isNaN(number)) {
        return null;
    }
    return Math.max(0, Math.min(100, number));
}

function deebotPartLabel(part) {
    return part.replace(/_/g, ' ');
}

if (typeof $ !== 'undefined' && $.widget && $.sv && $.sv.widget) {
    $.widget('sv.deebot_panel', $.sv.widget, {
        initSelector: '[data-widget="deebot.panel"]',

        // smartVISU then calls _update() with the changed item only, so one missing item does not blank the panel
        allowPartialUpdate: true,

        _create: function () {
            this._super();
            var element = this.element;
            this.targets = {};
            DEEBOT_PANEL_TARGETS.forEach(function (name) {
                this.targets[name] = element.attr('data-item-' + name.replace(/_/g, '-'));
            }, this);
            this.parts = (element.attr('data-parts') || '').split(',').filter(Boolean);
            this.names = DEEBOT_PANEL_FIELDS.concat(this.parts.map(function (part) {
                return 'lifespan_' + part;
            }));
            this.mapPage = element.attr('data-mappage') || '';
            this.values = {};
            this.roomsKey = null;
            this._build();
        },

        _send: function (name, value) {
            io.write(this.targets[name], value);
        },

        _button: function (text, title, onClick) {
            return $('<a href="#" class="ui-btn ui-mini ui-btn-inline ui-corner-all deebot-btn"></a>')
                .text(text).attr('title', title)
                .on('click', function (event) {
                    event.preventDefault();
                    onClick();
                });
        },

        _build: function () {
            var that = this;
            var row = function () {
                return $('<div class="deebot-row"></div>');
            };

            this.$state = $('<strong class="deebot-state"></strong>');
            this.$battery = $('<span class="deebot-battery"></span>');
            this.$error = $('<div class="deebot-row deebot-error"></div>');
            this.$station = $('<div class="deebot-row deebot-muted"></div>');

            this.$primary = this._button('', '', function () {
                that._send(deebotPrimaryAction(that.values.state).cmd, true);
            });
            var buttons = row().append(
                this.$primary,
                this._button('■', 'Stopp', function () { that._send('cmd_stop', true); }),
                this._button('⌂', 'Zur Station', function () { that._send('cmd_dock', true); }),
                this._button('♪', 'Orten', function () { that._send('cmd_locate', true); })
            );

            // the dropdowns are smartVISU basic.select widgets rendered by the macro
            var settings = this.element.children('.deebot-settings').detach();

            this.$stats = $('<div class="deebot-row deebot-muted"></div>');
            this.$parts = $('<div class="deebot-parts"></div>');

            this.$roomList = $('<div class="deebot-roomlist"></div>');
            this.$roomButton = this._button('Räume reinigen', 'Ausgewählte Räume reinigen', function () {
                var ids = that.$roomList.find('select').filter(function () {
                    return this.value === '1';
                }).map(function () {
                    return Number($(this).attr('data-room'));
                }).get();
                if (ids.length) {
                    that._send('cmd_clean_rooms', ids);
                    that._applyPreselection();
                }
            });
            this.$rooms = $('<div></div>').hide().append(this.$roomList, this.$roomButton);
            this.$roomToggle = this._button('Räume', 'Raumauswahl ein-/ausklappen', function () {
                that.$rooms.toggle();
            }).hide();

            // button of the map popup, rendered by the macro
            var mapOpen = this.element.children('.deebot-map-open').detach();
            this.$mapLink = this.mapPage
                ? $('<a class="ui-btn ui-mini ui-btn-inline ui-corner-all deebot-btn">Karte</a>').attr('href', this.mapPage)
                : $();

            this.element.append(
                row().append(this.$state, this.$battery),
                this.$error, this.$station, buttons, settings, this.$stats, this.$parts, this.$roomToggle, this.$mapLink, mapOpen, this.$rooms
            );
        },

        _update: function (response) {
            var that = this;
            this.names.forEach(function (name, index) {
                if (response[index] !== undefined && response[index] !== null) {
                    that.values[name] = response[index];
                }
            });
            this._render();
        },

        _render: function () {
            var v = this.values;
            var available = v.available === undefined ? undefined : Boolean(Number(v.available) || v.available === true);

            this.$state.text(deebotStateLabel(v.state, available))
                .attr('class', ('deebot-state ' + deebotStateClass(v.state, available)).trim());
            this.$battery.text(v.battery !== undefined ? v.battery + ' %' : '');
            this.$error.text(Number(v.error_code) ? v.error_text || 'Fehler ' + v.error_code : '');
            this.$station.text(v.station_state && v.station_state !== 'idle'
                ? 'Station: ' + String(v.station_state).replace(/_/g, ' ') : '');

            var primary = deebotPrimaryAction(v.state);
            this.$primary.text(primary.label).attr('title', primary.title);

            this.$stats.text(v.clean_area !== undefined
                ? 'Letzte Reinigung: ' + v.clean_area + ' m\u00B2 / ' + deebotMinutes(v.clean_time) : '');

            this._renderParts();
            this._renderRooms();
        },

        _renderParts: function () {
            var that = this;
            this.$parts.empty();
            this.parts.forEach(function (part) {
                var percent = deebotPercent(that.values['lifespan_' + part]);
                if (percent === null) { return; }
                that.$parts.append(
                    $('<div class="deebot-part"></div>').append(
                        $('<span></span>').text(deebotPartLabel(part) + ' ' + percent + ' %'),
                        $('<div class="deebot-bar"></div>').append(
                            $('<div class="deebot-bar-fill"></div>')
                                .toggleClass('deebot-low', percent < 15).css('width', percent + '%'))));
            });
        },

        /** Switches on the rooms flagged preselect and off all others. */
        _applyPreselection: function () {
            var preselected = {};
            deebotRooms(this.values.rooms).forEach(function (room) {
                preselected[room.id] = room.preselect;
            });
            this.$roomList.find('select').each(function () {
                var select = $(this).val(preselected[Number($(this).attr('data-room'))] ? '1' : '0');
                if ($.fn.flipswitch) { select.flipswitch('refresh'); }
            });
        },

        _renderRooms: function () {
            var rooms = deebotRooms(this.values.rooms);
            var key = JSON.stringify(rooms);
            if (key === this.roomsKey) { return; }
            this.roomsKey = key;
            this.$roomList.empty();
            var labels = deebotRoomLabels(rooms);
            rooms.forEach(function (room, index) {
                // same markup as smartVISU's basic.flip, so jQuery Mobile themes it as a switch
                var select = $('<select data-role="flipswitch"></select>').attr('data-room', room.id).append(
                    $('<option value="0">aus</option>'), $('<option value="1">an</option>'))
                    .val(room.preselect ? '1' : '0');
                this.$roomList.append($('<div class="deebot-room"></div>').append(
                    $('<span></span>').text(labels[index]), select));
                if ($.fn.flipswitch) { select.flipswitch(); }
            }, this);
            this.$roomToggle.toggle(rooms.length > 0);
            if (!rooms.length) { this.$rooms.hide(); }
        }
    });

    $.widget('sv.deebot_map', $.sv.widget, {
        initSelector: '[data-widget="deebot.map"]',

        _create: function () {
            this._super();
            this.$image = $('<img class="deebot-map" alt="">').hide();
            this.$empty = $('<span>Keine Karte verfügbar</span>');
            this.element.append(this.$image, this.$empty);
        },

        _update: function (response) {
            var svg = Array.isArray(response) ? response[0] : response;
            if (typeof svg === 'string' && svg.length) {
                this.$image.attr('src', 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svg)).show();
                this.$empty.hide();
            } else {
                this.$image.hide();
                this.$empty.show();
            }
        }
    });
}

if (typeof module !== 'undefined') {
    module.exports = {
        DEEBOT_PANEL_FIELDS: DEEBOT_PANEL_FIELDS,
        DEEBOT_PANEL_TARGETS: DEEBOT_PANEL_TARGETS,
        deebotPrimaryAction: deebotPrimaryAction,
        deebotStateLabel: deebotStateLabel,
        deebotStateClass: deebotStateClass,
        deebotRooms: deebotRooms,
        deebotRoomLabels: deebotRoomLabels,
        deebotMinutes: deebotMinutes,
        deebotPercent: deebotPercent,
        deebotPartLabel: deebotPartLabel
    };
}
