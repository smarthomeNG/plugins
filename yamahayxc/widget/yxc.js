// ----- yxc.device -----------------------------------------------------------

$.widget("sv.yxc_device", $.sv.widget, {

    initSelector: '[data-widget="yxc.device"]',

    options: {},

    _create: function() {
        this._super();
        var self = this;

        this.$badge = this.element.find('.yxc-unreachable-badge');
        this.$lastSeen = this.element.find('.yxc-unreachable-lastseen');
        this.$lastSeenText = this.element.find('.yxc-lastseen-text');
        this.$artPlaceholder = this.element.find('.yxc-art-placeholder');
        this.$artLive = this.element.find('.yxc-art-live');

        // Zone tab: switch active zone
        this._on(this.element.find('.yxc-zone-btn'), {
            'click': function(event) {
                event.preventDefault();
                event.stopPropagation();
                self._switchZone($(event.currentTarget).data('zone'));
            }
        });

        // DSP button: open DSP popup
        this._on(this.element.find('.yxc-dsp-btn'), {
            'click': function(event) {
                event.preventDefault();
                event.stopPropagation();
                $('#' + self.element.attr('id') + '-dsp-popup').popup('open');
            }
        });
    },

    _switchZone: function(zone) {
        var el = this.element;

        // Zone tab highlight
        el.find('.yxc-zone-btn').removeClass('icon1').addClass('icon0');
        el.find('.yxc-zone-btn[data-zone="' + zone + '"]').removeClass('icon0').addClass('icon1');

        // Volume sliders
        el.find('.yxc-vol-ctrl').hide();
        el.find('.yxc-vol-ctrl.yxc-zone-' + zone).show();

        // Mute + power buttons in bar
        el.find('.yxc-btn-ctrl').hide();
        el.find('.yxc-btn-ctrl.yxc-zone-' + zone).css('display', 'inline-block');
    },

    _update: function(response) {
        var input = String(response[0]);
        var reachable = !!Number(response[1]);
        var netusb = ['net_radio', 'server', 'airplay', 'bluetooth', 'spotify',
                      'pandora', 'siriusxm', 'tidal', 'deezer', 'qobuz',
                      'mc_link', 'usb', 'main_sync'];
        var isNetusb = netusb.indexOf(input) >= 0;
        var isTuner  = input === 'tuner';
        var isServer = input === 'server';

        this.element.find('.yxc-panel-netusb').toggle(isNetusb);
        this.element.find('.yxc-panel-tuner').toggle(isTuner);
        // repeat/shuffle/browse only make sense for the UPnP/DLNA media
        // server source - airplay/bluetooth/etc are external-app passthrough
        // with nothing on this device to browse or reorder
        this.element.find('.yxc-server-only').toggle(isServer);

        // dim only, never disable - writes are deliberately still allowed
        // while unreachable (plugin design: a manual retry costs nothing,
        // reachable is a staleness hint, not proof a write will fail)
        this.element.toggleClass('yxc-unreachable', !reachable);
        this.$badge.toggle(!reachable);
        this.$lastSeen.toggle(!reachable);

        // last_seen is a Python time.time() epoch in SECONDS (0 if the
        // device was never reachable since shng startup) - not run through
        // basic.print since that expects milliseconds and has no way to
        // special-case 0 as "never" rather than formatting it as a real date
        var lastSeen = Number(response[2]) || 0;
        if (lastSeen > 0) {
            var d = new Date(lastSeen * 1000);
            this.$lastSeenText.text(pad2(d.getHours()) + ':' + pad2(d.getMinutes()));
        }
        else {
            this.$lastSeenText.text('nie');
        }

        // the device drops its own albumarturl link once playback is fully
        // stopped, so the <img> 404s if left showing - swap to a static
        // placeholder then, without collapsing the space. Paused keeps the
        // art showing (track is still cued up, just not advancing) - only
        // 'stop' means there's nothing loaded anymore.
        var hasArt = String(response[3]) !== 'stop';
        this.$artPlaceholder.toggle(!hasArt);
        this.$artLive.toggle(hasArt);

        // powered off (main zone) is a different state than unreachable -
        // dim the now-irrelevant source/art/meta/netusb-controls, but keep
        // the bottom bar at full strength so the power button stays clearly
        // usable to turn it back on
        var power = !!Number(response[4]);
        this.element.toggleClass('yxc-poweroff', !power);
    }

});

function pad2(n) {
    return (n < 10 ? '0' : '') + n;
}


// ----- yxc.browse -----------------------------------------------------------
// UPnP/USB/DLNA list browser (getListInfo/setListControl) plus play queue and
// MC-playlist-bank management, driven by the netusb.browse.* / netusb.queue.*
// items. attribute bitmask on each browse.list entry (spec 7.9 + reverse-
// engineered extras): bit1(2)=selectable(folder), bit2(4)=playable,
// bit23(8388608)=Play Now, bit24(16777216)=Play Next, bit25(33554432)=Add to
// Queue, bit26(67108864)=Add to MC Playlist. Several rows can have multiple
// bits set at once (e.g. an album is select+play+play_now capable).
//
// Two separate index spaces: browse.* actions (select/play/play_now/
// play_next/queue_add/playlist_add) all use the position within the
// currently browsed folder (browse.index + row offset). queue.* actions
// (play/delete) use the position within the play queue itself - never mix
// the two.
//
// playlist_bank must be written before playlist_add/playlist_rename/
// playlist_clear/queue.save_playlist or the plugin silently no-ops - this
// widget tracks the last-selected bank in this.playlistBank and disables
// those actions client-side until one has been picked via the Playlists
// popup.
//
// "Up"/"Home"/breadcrumb clicks all reduce to writing browse.return
// repeatedly, stepping again only once the previous fetch's busy flag has
// cleared, since return only moves one layer at a time and the cursor is
// shared with other clients/apps.

$.widget("sv.yxc_browse", $.sv.widget, {

    initSelector: '[data-widget="yxc.browse"]',

    options: {},

    _create: function() {
        this._super();
        var self = this;

        this.itemPage = this.element.data('itemPage');
        this.itemSelect = this.element.data('itemSelect');
        this.itemPlay = this.element.data('itemPlay');
        this.itemReturn = this.element.data('itemReturn');
        this.itemPlayNow = this.element.data('itemPlayNow');
        this.itemPlayNext = this.element.data('itemPlayNext');
        this.itemQueueAdd = this.element.data('itemQueueAdd');
        this.itemPlaylistBank = this.element.data('itemPlaylistBank');
        this.itemPlaylistAdd = this.element.data('itemPlaylistAdd');
        this.itemPlaylistRename = this.element.data('itemPlaylistRename');
        this.itemPlaylistClear = this.element.data('itemPlaylistClear');
        this.itemQueuePlay = this.element.data('itemQueuePlay');
        this.itemQueueDelete = this.element.data('itemQueueDelete');
        this.itemQueueClear = this.element.data('itemQueueClear');
        this.itemQueueUpdate = this.element.data('itemQueueUpdate');
        this.itemQueueSavePlaylist = this.element.data('itemQueueSavePlaylist');

        // sibling popups share this widget's uid prefix (browse-body's own
        // id is "<uid>-browse")
        var uidBase = this.element.attr('id').replace(/-browse$/, '');

        var popup = this.element.closest('[data-role="popup"]');
        this.$home = popup.find('.yxc-browse-home');
        this.$up = popup.find('.yxc-browse-up');
        this.$title = popup.find('.yxc-browse-title');
        this.$crumbs = popup.find('.yxc-browse-crumbs');
        this.$list = this.element.find('.yxc-browse-list');
        this.$busy = this.element.find('.yxc-browse-busy');
        this.$prev = popup.find('.yxc-browse-prev');
        this.$next = popup.find('.yxc-browse-next');
        this.$range = popup.find('.yxc-browse-range');

        this.$rowActionPopup = $('#' + uidBase + '-rowaction-popup');
        this.$rowActionTitle = this.$rowActionPopup.find('.yxc-rowaction-title');
        this.$rowActionPlaynow = this.$rowActionPopup.find('.yxc-rowaction-playnow');
        this.$rowActionPlaynext = this.$rowActionPopup.find('.yxc-rowaction-playnext');
        this.$rowActionQueueadd = this.$rowActionPopup.find('.yxc-rowaction-queueadd');
        this.$rowActionPlaylistadd = this.$rowActionPopup.find('.yxc-rowaction-playlistadd');

        this.$queuePopup = $('#' + uidBase + '-queue-popup');
        this.$queueTitle = this.$queuePopup.find('.yxc-queue-title');
        this.$queueList = this.$queuePopup.find('.yxc-queue-list');
        this.$queueUpdate = this.$queuePopup.find('.yxc-queue-update');
        this.$queueClear = this.$queuePopup.find('.yxc-queue-clear');
        this.$queueSavePlaylist = this.$queuePopup.find('.yxc-queue-saveplaylist');
        this.$queuePlaylistBtn = this.$queuePopup.find('.yxc-queue-playlist-btn');

        this.$playlistPopup = $('#' + uidBase + '-playlist-popup');
        this.$playlistList = this.$playlistPopup.find('.yxc-playlist-list');

        this.crumbs = [];
        this.busy = false;
        this.targetLayer = null;
        this.pendingRowIdx = null;
        this.playlistBank = null;

        // Browse/Queue are separate top-level buttons on the main panel
        // (jQuery Mobile 1.4.5 doesn't reliably open a second popup while
        // one is already open), but Playlists only makes sense as a
        // sub-action of Queue ("save queue as playlist") - for this one
        // nested hop, close Queue first and only open Playlists once that
        // close has actually finished animating.
        this.$queuePlaylistBtn.on('click', function(e) {
            e.preventDefault();
            self.$queuePopup.one('popupafterclose', function() {
                self.$playlistPopup.popup('open');
            });
            self.$queuePopup.popup('close');
        });

        this.$home.on('click', function(e) {
            e.preventDefault();
            self._goTo(0);
        });

        this.$up.on('click', function(e) {
            e.preventDefault();
            self._goTo(Math.max(0, (self.curLayer || 0) - 1));
        });

        this.$crumbs.on('click', '.yxc-browse-crumb', function(e) {
            e.preventDefault();
            self._goTo(Number($(this).attr('data-layer')));
        });

        this.$prev.on('click', function(e) {
            e.preventDefault();
            if (self.busy || self.curIndex <= 0) return;
            io.write(self.itemPage, Math.max(0, self.curIndex - 8));
        });

        this.$next.on('click', function(e) {
            e.preventDefault();
            if (self.busy || (self.curIndex + 8) >= self.maxLine) return;
            io.write(self.itemPage, self.curIndex + 8);
        });

        // play/kebab buttons are nested inside a selectable row - stop the
        // click from also triggering the row's own select handler
        this.$list.on('click', '.yxc-browse-row-play', function(e) {
            e.preventDefault();
            e.stopImmediatePropagation();
            if (self.busy) return;
            io.write(self.itemPlay, Number($(this).attr('data-idx')));
            // no queue concept for a plain play tap - playing a track
            // replaces what's currently playing, nothing left to browse for
            popup.popup('close');
        });

        this.$list.on('click', '.yxc-browse-row-kebab', function(e) {
            e.preventDefault();
            e.stopImmediatePropagation();
            if (self.busy) return;
            var absIdx = Number($(this).attr('data-idx'));
            var entry = (self.curList || [])[absIdx - self.curIndex];
            if (!entry) return;
            self.pendingRowIdx = absIdx;
            self._openRowActions(entry);
        });

        this.$list.on('click', '.yxc-browse-row-select', function(e) {
            if (self.busy) return;
            io.write(self.itemSelect, Number($(this).attr('data-idx')));
        });

        // browse.* items are only ever populated by an actual browse action,
        // and the cursor is shared with other clients/apps, so re-request
        // the current page fresh every time this popup is opened rather
        // than trusting whatever was last rendered
        popup.on('popupafteropen', function() {
            if (!self.busy)
                io.write(self.itemPage, 0);
        });

        // ---- row-action popup (play now / play next / queue add / playlist add) ----

        this.$rowActionPlaynow.on('click', function(e) {
            e.preventDefault();
            if (self.pendingRowIdx == null) return;
            io.write(self.itemPlayNow, self.pendingRowIdx);
            self.$rowActionPopup.popup('close');
        });

        this.$rowActionPlaynext.on('click', function(e) {
            e.preventDefault();
            if (self.pendingRowIdx == null) return;
            io.write(self.itemPlayNext, self.pendingRowIdx);
            self.$rowActionPopup.popup('close');
        });

        this.$rowActionQueueadd.on('click', function(e) {
            e.preventDefault();
            if (self.pendingRowIdx == null) return;
            io.write(self.itemQueueAdd, self.pendingRowIdx);
            self.$rowActionPopup.popup('close');
        });

        this.$rowActionPlaylistadd.on('click', function(e) {
            e.preventDefault();
            if (self.pendingRowIdx == null || self.playlistBank == null) return;
            io.write(self.itemPlaylistAdd, self.pendingRowIdx);
            self.$rowActionPopup.popup('close');
        });

        // ---- queue popup ----

        this.$queuePopup.on('popupafteropen', function() {
            io.write(self.itemQueueUpdate, true);
        });

        this.$queueList.on('click', '.yxc-queue-row-delete', function(e) {
            e.preventDefault();
            e.stopImmediatePropagation();
            io.write(self.itemQueueDelete, Number($(this).attr('data-idx')));
        });

        this.$queueList.on('click', '.yxc-queue-row', function(e) {
            io.write(self.itemQueuePlay, Number($(this).attr('data-idx')));
        });

        this.$queueUpdate.on('click', function(e) {
            e.preventDefault();
            io.write(self.itemQueueUpdate, true);
        });

        this.$queueClear.on('click', function(e) {
            e.preventDefault();
            if (!window.confirm('Warteschlange wirklich leeren?')) return;
            io.write(self.itemQueueClear, true);
        });

        this.$queueSavePlaylist.on('click', function(e) {
            e.preventDefault();
            if (self.playlistBank == null) {
                window.alert('Bitte zuerst eine Ziel-Playlist wählen (Symbol oben rechts).');
                return;
            }
            io.write(self.itemQueueSavePlaylist, true);
        });

        // ---- playlist bank popup ----

        this.$playlistList.on('click', '.yxc-playlist-row-edit', function(e) {
            e.preventDefault();
            e.stopImmediatePropagation();
            var bank = Number($(this).attr('data-bank'));
            var current = (self.playlistNames || [])[bank - 1] || '';
            var name = window.prompt('Neuer Name für Playlist ' + bank + ':', current);
            if (name === null || name === '') return;
            self.playlistBank = bank;
            io.write(self.itemPlaylistBank, bank);
            io.write(self.itemPlaylistRename, name);
        });

        this.$playlistList.on('click', '.yxc-playlist-row-delete', function(e) {
            e.preventDefault();
            e.stopImmediatePropagation();
            var bank = Number($(this).attr('data-bank'));
            if (!window.confirm('Inhalt von Playlist ' + bank + ' wirklich leeren?')) return;
            self.playlistBank = bank;
            io.write(self.itemPlaylistBank, bank);
            io.write(self.itemPlaylistClear, true);
        });

        this.$playlistList.on('click', '.yxc-playlist-row-select', function(e) {
            var bank = Number($(this).attr('data-bank'));
            self.playlistBank = bank;
            io.write(self.itemPlaylistBank, bank);
            self._renderPlaylists();
        });
    },

    _goTo: function(targetLayer) {
        this.targetLayer = targetLayer;
        if (!this.busy && this.curLayer > targetLayer)
            io.write(this.itemReturn, true);
    },

    _openRowActions: function(entry) {
        var attr = Number(entry.attribute) || 0;

        this.$rowActionTitle.text(entry.text || '');
        this.$rowActionPlaynow.toggle((attr & (1 << 23)) !== 0);
        this.$rowActionPlaynext.toggle((attr & (1 << 24)) !== 0);
        this.$rowActionQueueadd.toggle((attr & (1 << 25)) !== 0);

        var canPlaylist = (attr & (1 << 26)) !== 0;
        this.$rowActionPlaylistadd.toggle(canPlaylist);
        this.$rowActionPlaylistadd.toggleClass('ui-state-disabled', this.playlistBank == null);
        this.$rowActionPlaylistadd.find('.yxc-rowaction-playlistadd-label').text(
            this.playlistBank == null
                ? 'Zu Playlist hinzufügen (erst Playlist wählen)'
                : 'Zu Playlist ' + this.playlistBank + ' hinzufügen'
        );

        this.$rowActionPopup.popup('open');
    },

    _update: function(response) {
        var list = response[0] || [];
        var menuName = response[1] || '';
        var menuLayer = Number(response[2]);
        var maxLine = Number(response[3]);
        var index = Number(response[4]);
        var playingIndex = Number(response[5]);
        var busy = !!response[6];
        var queueList = response[7] || [];
        var queueMaxLine = Number(response[8]);
        var queuePlayingIndex = Number(response[9]);
        var playlistNames = response[10] || [];

        var wasBusy = this.busy;
        var hadLayer = this.curLayer;

        if (hadLayer != null) {
            if (menuLayer > hadLayer) {
                this.crumbs.push({name: this.curMenuName, layer: hadLayer});
            }
            else if (menuLayer < hadLayer) {
                while (this.crumbs.length && this.crumbs[this.crumbs.length - 1].layer >= menuLayer)
                    this.crumbs.pop();
            }
        }

        this.busy = busy;
        this.curLayer = menuLayer;
        this.curIndex = index;
        this.maxLine = maxLine;
        this.playingIndex = playingIndex;
        this.curMenuName = menuName;
        this.curList = list;
        this.queueList = queueList;
        this.queueMaxLine = queueMaxLine;
        this.queuePlayingIndex = queuePlayingIndex;
        this.playlistNames = playlistNames;

        this._render();
        this._renderQueue();
        this._renderPlaylists();

        if (wasBusy && !busy && this.targetLayer != null) {
            if (this.curLayer <= this.targetLayer)
                this.targetLayer = null;
            else
                io.write(this.itemReturn, true);
        }
    },

    _render: function() {
        var self = this;
        var CONTEXT_BITS = (1 << 23) | (1 << 24) | (1 << 25) | (1 << 26);

        this.$title.text(this.curMenuName);
        this.$up.toggleClass('ui-state-disabled', this.busy || this.curLayer <= 0);
        this.$home.toggleClass('ui-state-disabled', this.busy || this.curLayer <= 0);

        this.$crumbs.empty();
        this.crumbs.forEach(function(c) {
            $('<a class="yxc-browse-crumb ui-btn ui-mini ui-corner-all ui-btn-inline"></a>')
                .text(c.name || ('Ebene ' + c.layer))
                .attr('data-layer', c.layer)
                .appendTo(self.$crumbs);
        });

        this.$list.empty();
        (this.curList || []).forEach(function(entry, i) {
            var absIdx = self.curIndex + i;
            var attr = Number(entry.attribute) || 0;
            var canSelect = (attr & 2) !== 0;
            var canPlay = (attr & 4) !== 0;
            var hasContextActions = (attr & CONTEXT_BITS) !== 0;

            var row = $('<div class="yxc-browse-row"></div>').attr('data-idx', absIdx);
            if (self.playingIndex >= 0 && absIdx === self.playingIndex)
                row.addClass('yxc-browse-playing');
            if (!canSelect && !canPlay)
                row.addClass('yxc-browse-disabled');
            if (canSelect)
                row.addClass('yxc-browse-row-select');

            row.append($('<div class="yxc-browse-text"></div>').text(entry.text || ''));
            if (entry.subtexts && entry.subtexts.length)
                row.append($('<div class="yxc-browse-subtext"></div>').text(entry.subtexts.join(' / ')));

            if (canPlay) {
                $('<a class="yxc-browse-row-play ui-btn ui-mini ui-corner-all ui-nodisc-icon">&#9654;</a>')
                    .attr('data-idx', absIdx)
                    .appendTo(row);
            }
            if (hasContextActions) {
                $('<a class="yxc-browse-row-kebab ui-btn ui-mini ui-corner-all ui-nodisc-icon">&#8942;</a>')
                    .attr('data-idx', absIdx)
                    .appendTo(row);
            }

            self.$list.append(row);
        });

        var shown = (this.curList || []).length;
        var from = shown ? this.curIndex + 1 : 0;
        var to = this.curIndex + shown;
        this.$range.text(from + '–' + to + ' / ' + this.maxLine);
        this.$prev.toggleClass('ui-state-disabled', this.busy || this.curIndex <= 0);
        this.$next.toggleClass('ui-state-disabled', this.busy || (this.curIndex + 8) >= this.maxLine);

        this.$busy.toggle(!!this.busy);
        this.$list.toggleClass('yxc-browse-dim', !!this.busy);
    },

    _renderQueue: function() {
        var self = this;

        this.$queueTitle.text('Warteschlange (' + (this.queueMaxLine || 0) + ')');

        this.$queueList.empty();
        (this.queueList || []).forEach(function(entry, i) {
            var row = $('<div class="yxc-queue-row"></div>').attr('data-idx', i);
            if (self.queuePlayingIndex >= 0 && i === self.queuePlayingIndex)
                row.addClass('yxc-queue-playing');

            row.append($('<div class="yxc-queue-text"></div>').text(entry.text || ''));
            $('<a class="yxc-queue-row-delete ui-btn ui-mini ui-corner-all ui-nodisc-icon">&#10005;</a>')
                .attr('data-idx', i)
                .appendTo(row);

            self.$queueList.append(row);
        });
    },

    _renderPlaylists: function() {
        var self = this;

        this.$playlistList.empty();
        for (var i = 0; i < 5; i++) {
            var bank = i + 1;
            var name = (this.playlistNames || [])[i] || '(leer)';

            var row = $('<div class="yxc-playlist-row yxc-playlist-row-select"></div>').attr('data-bank', bank);
            if (this.playlistBank === bank)
                row.addClass('yxc-playlist-selected');

            row.append($('<div class="yxc-playlist-text"></div>').text(bank + ': ' + name));
            $('<a class="yxc-playlist-row-edit ui-btn ui-mini ui-corner-all ui-nodisc-icon">&#9998;</a>')
                .attr('data-bank', bank)
                .appendTo(row);
            $('<a class="yxc-playlist-row-delete ui-btn ui-mini ui-corner-all ui-nodisc-icon">&#128465;</a>')
                .attr('data-bank', bank)
                .appendTo(row);

            self.$playlistList.append(row);
        }
    }

});
