
class CellView {
  constructor(args) {
    // $element, config, app
    this.$element = args.$element;
    this.config = args.config;
    this.app = args.app;
    this.active = false;
    this.pubsub = args.pubsub;

    // console.log('args', args);

    this.setContent(this.app.emojiWithName(this.config.emoji));
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
    $element.on('click',     () => this.pubsub.submit('Cell.Press',       {Cell: this}));
    $element.on('dblclick',  () => this.pubsub.submit('Cell.DoublePress', {Cell: this}));
    $element.on('doubletap', () => this.pubsub.submit('Cell.DoublePress', {Cell: this}));
  }

  setContent(c) {
    this.$element.children('.content').html(c);
  }

  onMessage(e) {
  }

  getValues() {
    if (!this.config.getValues) { return; }
    var url = this.config.getValues.url;
    if (!url) { return; }
    var self = this;
    var data = this.app.request(url).done(function(resp){
      self.setContent(resp);
    });
  }

  togglesRoom() {
    return this.config.togglesRoom;
  }

  isActiveForRoom(room) {
    return this.config.activeWhenRoom === room;
  }

  isActive() {
    return this.active;
  }

  setActive(isActive) {
    var existing = this.active;
    if (isActive == existing) {
      return;
    }
    if (isActive) {
      this.$element.addClass('active');
    }
    else {
      this.$element.removeClass('active');
    }
    this.active = isActive;
  }
}
