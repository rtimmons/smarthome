
class Cell {
  constructor(args) {
    // $element, config, app
    this.$element = args.$element;
    this.config = args.config;
    this.app = args.app;

    // console.log('args', args);

    // TODO: do we need .data if we have this as a separate class now?
    this.$element.data('config', this.config);
    this.$element.html(this.app.emojiWithName(this.config.emoji));
    this.$element.addClass(this.config.claz || '');

    var $cell = this.$element;

    var tapped = false;
    var app = this.app;
    // hacky thing to bind double-tap
    $cell.on("touchstart",function(e){
      if(!tapped){
        tapped=setTimeout(function(){
          tapped=null;
          $cell.click();
        },300);
      } else {
        clearTimeout(tapped);
        tapped=null;
        $cell.doubleClick();
      }
      e.preventDefault();
    });

    $cell.click(() => app.submit('Cell.Click', {Cell: $cell}));
    $cell.dblclick(() => app.submit('Cell.DoubleClick', {Cell: $cell}));
    $cell.on('doubletap', () => app.submit('Cell.DoubleClick', {Cell: $cell}));
  }
}
