class Grid {
  constructor($element, config) {
    this.$element = $element;
    this.cols = config.cols;
    this.rows = config.rows;
  }
  render() {
    for(var row=0; row<this.rows; row++) {
      for(var col=0; col<this.cols; col++) {
        var cell = $('<div class="cell">');
        cell.addClass('row-'+row);
        cell.addClass('col-'+col);
        cell.attr('id', 'cell-'+row+'-'+col);
        this.$element.append(cell);
        cell.dblclick(function() { console.log($(this).attr('id')) });
      }
    }
  }

  resize(width, height) {
    var square = Math.min(width/this.cols, height/this.rows);
    this.square = square;
    $('.cell').css({
      height: (square) + 'px',
      width: (square) + 'px',
      fontSize: (square * 2 / 3) + 'px',
      lineHeight: (square) + 'px',
    });

    this.$element.width((square + 2) * this.cols);
  }
}

$(function(){
  var grid = new Grid($('#grid'), config);
  grid.render();

  var win = $(window);
  win.resize(function(){
    grid.resize(win.width(), win.height());
  })
  .resize();
});

