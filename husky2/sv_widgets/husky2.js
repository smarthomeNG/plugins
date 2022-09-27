
$.widget("sv.husky2", $.sv.widget, {
    initSelector: 'div[data-widget="husky2.map"]',

    options: {
		mapskey: '',
        zoomlevel: 19,
        pathcolor: '#3afd02',
	},

    _create: function () {
        this._super();
        this._create_map();
    },

    _create_map: function () {
        try {
            this.map = new google.maps.Map(this.element[0], {
                zoom: this.options.zoomlevel,
                mapTypeId: 'hybrid',
                center: new google.maps.LatLng(0.0, 0.0),
         });
        }
        catch (e) {
            if (e.name == "ReferenceError") { // google maps script not loaded yet
                var that = this;
                // google maps script is already loading in another widget
                if (window.google_maps_loading) {
                    window.setTimeout(function () {
                        that._create_map()
                    }, 100)
                    return;
                }
                // google maps script is not loading
                window.google_maps_loading = true;
                $.ajax({
                    url: 'https://maps.googleapis.com/maps/api/js?key=' + this.options.mapskey + '&language=de',
                    dataType: "script",
                    complete: function () {
                        window.google_maps_loading = false;
                        that._create_map()
                    }
                });
                return;
            }
            else  // other exceptions should be thrown
                throw e;
        }

    this.marker_myself = new google.maps.Marker({
        map: this.map,
        position: new google.maps.LatLng(0.0, 0.0),
        icon: '',
        title:'',
        zIndex:99999999
    });

    this.linePath = new google.maps.Polyline({
      path: [],
      strokeColor: this.options.pathcolor,
      strokeOpacity: 0.6,
      strokeWeight: 2,
      map: this.map
    });


    },

    _update: function(response) {
        if(!this.map) {
            var that = this;
            window.setTimeout(function() { that._update(response) }, 100)
            return;
        }

        this.marker_myself.setTitle(response[3]);

        var pos = new google.maps.LatLng(parseFloat(response[0]),parseFloat(response[1]));

        this.map.setCenter(pos);
        this.marker_myself.setPosition(pos);

        var coord = [];
        for (const point of response[2]){
            coord.push(new google.maps.LatLng(parseFloat(point[0]),parseFloat(point[1])));
        }
        this.linePath.setPath(coord);

    }
});
