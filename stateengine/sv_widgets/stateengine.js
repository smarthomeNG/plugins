// ----- stateenginestatus ------------------------------------------------------

$.widget("sv.stateengine", $.sv.widget, {

  initSelector: '[data-widget="stateengine.state"]',

  options: {
  },
  _create: function() {
    console.log('Short press lock '+this.element.attr('rel'));
    this._super();
    var shortpressEvent = function(event) {
        try {
          list_val = list_val;
          idx = idx;
        }
        catch {
          list_val = ['locked'];
          idx = 0;
        }
        if (this.element.attr('lock-item') == '' && this.element.attr('release-item') == '') {
        $("#"+this.element.attr('rel')).popup( "open" );
        }
        else if (list_val[idx] == 'locked' && this.element.attr('lock-item') != ''){
            io.write(this.element.attr('lock-item'), (this.element.val() == this.element.attr('data-val-on') ? this.element.attr('data-val-off') : this.element.attr('data-val-on')) );
            console.log('Short press lock '+this.element.attr('rel'));
        }
        else if (list_val[idx] == 'suspended' && this.element.attr('release-item') != ''){
            io.write(this.element.attr('release-item'), true );
            console.log('Short press release '+this.element.attr('rel'));
        }
        else {
            io.write(this.element.attr('lock-item'), (this.element.val() == this.element.attr('data-val-on') ? this.element.attr('data-val-off') : this.element.attr('data-val-on')) );
            console.log('Short press else '+this.element.val()+', setting lock item '+ this.element.attr('lock-item'));
        }
    }

    if(this.element.attr('rel')) {
      this._on(this.element.find('a[data-widget="stateengine.state"]'), {
        'tap': shortpressEvent,
        'taphold': function (event) {
          event.preventDefault();
          event.stopPropagation();
          event.stopImmediatePropagation();
          console.log('Long press '+this.element.attr('rel'));

          $("#"+this.element.attr('rel')).popup( "open" );
          return false;
        }
      });
    }
    else { // if no longpress item is passed, use shortpress event on click
      this._on(this.element.find('a[data-widget="stateengine.state"]'), {
        'click': shortpressEvent,
        'tap': shortpressEvent
      });
    }
  },
  _update: function (response) {
    // get list of values and images
     list_val = this.element.attr('data-vals').explode();
     list_img = this.element.attr('data-img').explode();

    // get the index of the value received
    idx = list_val.indexOf(response.toString());

    // update the image
   this.element.children().hide()
   this.element.find('[data-val="' + response.toString() + '"]').show();
    console.log('ID '+this.element.attr('id')+' image '+list_img[idx]);

    // memorise the index for next use
    this.element.val(idx);
  }

});
