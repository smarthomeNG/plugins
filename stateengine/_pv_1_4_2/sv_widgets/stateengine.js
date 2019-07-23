// ----- stateenginestatus ------------------------------------------------------

$.widget("sv.stateengine", $.sv.widget, {

  initSelector: '[data-widget="stateengine.state"]',

  options: {

  },
  _update: function (response) {
    // get list of values and images
    list_val = this.element.attr('data-vals').explode();
    list_img = this.element.attr('data-img').explode();

    // get the index of the value received
    idx = list_val.indexOf(response.toString());

    // update the image
    $('#' + this.element.attr("id") + ' img').attr('src', list_img[idx]);

        $('#' + this.element.attr("id")).show();
        console.log('ID '+this.element.attr('id')+' image '+list_img[idx]);
    // memorise the index for next use
    this.element.val(idx);
  },

    _events: {
    'taphold': function (event, response) {
        event.preventDefault();
        event.stopPropagation();
        console.log('Long press '+this.element.attr('rel'));

        $("#"+this.element.attr('rel')).popup( "open" );
        return false;
    },
  'tap': function (event, response) {
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
    }

});
