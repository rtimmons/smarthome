class Grid {
  constructor(args) {
    this.$element = args.container;
    var config = args.config;

    this.cells = [];
    this.cols = config.cols;
    this.rows = config.rows;
  }

  onResize(width, height) {
    var square = Math.min(width/this.cols, height/this.rows);
    this.square = square;
    $('.cell').each(function() {
      var t =$(this);
      t.css({
        height: ((t.attr('rowspan') || 1) * square) + 'px',
        width:  ((t.attr('colspan') || 1) * square) + 'px',
        fontSize: (square * 2 / 3) + 'px',
        lineHeight: (square) + 'px',
      });
    });

    this.$element.width((square + 2) * this.cols);
  }

  cell(row, col) {
    return this.$element.find('#cell-'+row+'-'+col);
  }

  assign(size, emoji, callback) {
    var cell = this.cell(size.y,size.x);
    cell.html(emoji);
    cell.click(() => callback());
  }

  init($win) {
    var grid = this;

    for(var row=0; row<this.rows; row++) {
      var tr = $('<tr>');
      for(var col=0; col<this.cols; col++) {
        var cell = $('<td class="cell">');
        cell.addClass('row-'+row);
        cell.addClass('col-'+col);
        cell.attr('id', 'cell-'+row+'-'+col);
        tr.append(cell);
        cell.dblclick(function() { console.log($(this).attr('id')) });
        this.cells.push(cell);
      }
      this.$element.append(tr);
    }

    $win.resize(function(){
      grid.onResize($win.width(), $win.height());
    }).resize();
  }
}