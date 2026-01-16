// ----- stateenginestatus ------------------------------------------------------

$.widget("sv.stateengine", $.sv.widget, {

  initSelector: '[data-widget="stateengine.state"]',

  options: {
  },
  _create: function() {
    this._super();
    var shortpressEvent = function(event) {
        try {
          list_val = this.element.attr('data-vals').explode();
          idx = this.element.val();
        }
        catch {
          list_val = [this.element.attr('data-lockname')];
          idx = 0;

        }

        if (this.element.attr('lock-item') == '' && this.element.attr('release-item') == '') {
        $("#"+this.element.attr('rel')).popup( "open" );
        }
        else if (this.element.attr('data-value') == this.element.attr('data-lockname') && this.element.attr('lock-item') != ''){
            console.log('Stateengine: Short press lock '+this.element.attr('lock-item'));
            io.write(this.element.attr('lock-item'), this.element.attr('data-val-off'));

        }
        else if (this.element.attr('data-value') == this.element.attr('data-suspendname') && this.element.attr('release-item') != ''){
            console.log('Stateengine: Short press release '+this.element.attr('release-item'));
            io.write(this.element.attr('release-item'), true );

        }
        else {
            console.log('Stateengine: Short press else '+this.element.val()+', setting lock item '+ this.element.attr('lock-item'));
            io.write(this.element.attr('lock-item'), this.element.attr('data-val-on') );
        }
    }

    if(this.element.attr('rel')) {
      this._on(this.element.find('a[data-widget="stateengine.state"]'), {
        'tap': shortpressEvent,
        'taphold': function (event) {
          event.preventDefault();
          event.stopPropagation();
          event.stopImmediatePropagation();
          console.log('Stateengine: Long press '+this.element.attr('rel'));

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
    console.log('Stateengine: Element with ID '+this.element.attr('id')+', image '+list_img[idx]);

    // memorise the index for next use
    this.element.val(idx);
    this.element.attr('data-value', list_val[idx]);
  }

});
