
class CellView {
  constructor(args) {
    // $element, config, app
    this.$element = args.$element;
    this.config = args.config;
    this.app = args.app;

    // console.log('args', args);

    this.$element.html(this.app.emojiWithName(this.config.emoji));
    this.$element.addClass(this.config.claz || '');

    // hacky thing to bind double-tap
    var $element = this.$element;
    var tapped = false;
    $element.on('touchstart', function(e) {
      if(!tapped){
        tapped = setTimeout(function(){
          tapped = null;
          $element.trigger('click');
        }, 300);
      } else {
        clearTimeout(tapped);
        tapped = null;
        $element.trigger('dblclick');
      }
      e.preventDefault();
    });

    var app = this.app;
    $element.on('click',     () => app.submit({Name: 'Cell.Press',       Cell: this }));
    $element.on('dblclick',  () => app.submit({Name: 'Cell.DoublePress', Cell: this }));
    $element.on('doubletap', () => app.submit({Name: 'Cell.DoublePress', Cell: this }));
  }

  isActiveForRoom(room) {
    return this.config.activeWhenRoom === room;
  }

  setActive(isActive) {
    if (isActive) {
      this.$element.addClass('active');
    }
    else {
      this.$element.removeClass('active');
    }
  }
}
