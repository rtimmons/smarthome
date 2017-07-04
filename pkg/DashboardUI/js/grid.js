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

  allCells() {
    return this.cells;
  }

  cell(size) {
    var cell = this.$element.find('#cell-'+size.y+'-'+size.x)

    if(size.w == 0 || size.h == 0) {
      cell.remove();
    }
    else {
      cell.attr('colspan', size.w);
    }

    this.cells.push(cell);
    return cell;
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
