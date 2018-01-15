
class Cell {
  constructor(args) {
    // $element, config, app
    this.$element = args.$element;
    this.config = args.config;
    this.app = args.app;

    // console.log('args', args);

    this.$element.html(this.app.emojiWithName(this.config.emoji));
    this.$element.addClass(this.config.claz || '');

    var $cell = this.$element;

    // hacky thing to bind double-tap
    var tapped = false;
    $cell.on('touchstart', function(e) {
      if(!tapped){
        tapped = setTimeout(function(){
          tapped = null;
          $cell.trigger('click');
        }, 300);
      } else {
        clearTimeout(tapped);
        tapped = null;
        $cell.trigger('dblclick');
      }
      e.preventDefault();
    });

    var app = this.app;
    $cell.on('click',     () => app.submit({Name: 'Cell.Click',       Cell: this }));
    $cell.on('dblclick',  () => app.submit({Name: 'Cell.DoubleClick', Cell: this }));
    $cell.on('doubletap', () => app.submit({Name: 'Cell.DoubleClick', Cell: this }));
  }
}
