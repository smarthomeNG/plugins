(function( $, window, document, undefined ) {
	var Reload = function(elem, options) {
		this.$elem = $(elem);
		this.options = options;
	};

	Reload.prototype.defaults = {
		time: 3000,
		autoReload: false,
		beforeReload: function(){},
		afterReload: function(){}
	};

	Reload.prototype.init = function() {
		var self = this;

		// Set the configuration parameters
		self.config = $.extend({},self.defaults,self.options);

		// Set the container for refresh animation
		self.config.refreshContainer = $(self.config.refreshContainer) || self.$elem.find('.refresh-container');

		// Set the container to update the data with
		self.config.dataContainer = $(self.config.dataContainer) || self.$elem.find('.data-container');
		
		self.$elem.find('.fa-refresh').click(self.reload());

		if(self.config.autoReload) {
			setInterval(self.reload,self.config.time);
		}

		return self;
	};

	Reload.prototype.reload = function(){
		var _self = this;
		_self.$elem.find('.fa-refresh').addClass('fa-spin');
		_self.cofig.refreshContainer.fadeIn();

		// Send the AJAX request to fetch the data
		$.ajax({
			url: _self.$elem.data('url'),
			async: true,
			beforeSend: _self.config.beforeReload,
			success: function(data) {
				_self.config.dataContainer.html(data);
				_self.config.afterReload();
			}

		});

	};

	// Register the plugin to JQuery
	$.fn.reload = function(options) {
		this.each(function() {
			var $this, reload;
			$this = $(this);
			reload = new Reload(this, options);
			return reload.init();

		});
	};

})( window.jQuery, window, document );