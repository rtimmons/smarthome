class GridView {
  constructor(args) {
    this.$element = args.container;
    var config = args.config;
    this.config = config;

    this.cells = [];
    this.cols = config.cols;
    this.rows = config.rows;
    this.zoneCells = {};
  }

  allCells() {
    return this.cells;
  }

  onResize(width, height) {
    var square = Math.min(width/this.cols, height/this.rows);
    this.square = square;
    $('.cell').each(function() {
      var t =$(this);
      var width = ((t.attr('colspan') || 1) * square) + 'px';
      t.css({
        height: ((t.attr('rowspan') || 1) * square) + 'px',
        width:  width,
        maxWidth: width,
        fontSize: (square * 2 / 3) + 'px',
        lineHeight: (square) + 'px',
      });
    });

    this.$element.width((square + 2) * this.cols);
  }

  getValues() {
    this.allCells().forEach(c => c.getValues());
  }

  // TODO: each cell is a listener
  updateZones(onoff) {
    // could optimize in the future
    this.allCells().forEach(c => {
      var room = c.togglesRoom();
      if (!room) {
        return;
      }
      c.setActive(
        onoff.on.indexOf(c.togglesRoom()) >= 0
      );
    });
  }

  _createElement(size) {
    var cell = this.$element.find('#cell-'+size.y+'-'+size.x)

    if(size.w == 0 || size.h == 0) {
      cell.remove();
    }
    else {
      cell.attr('colspan', size.w);
    }
    return cell;
  }

  init($win, app) {
    this.app = app;
    var grid = this;

    for(var row=0; row<this.rows; row++) {
      var tr = $('<tr>');
      for(var col=0; col<this.cols; col++) {
        var cell = $('<td class="cell">');
        // cell.addClass('row-'+row);
        // cell.addClass('col-'+col);
        cell.attr('id', 'cell-'+row+'-'+col);
        var span = $('<div class="content"></div>');
        cell.append(span);
        tr.append(cell);
      }
      this.$element.append(tr);
    }

    this.config.cells.forEach(b => {
      var cell = new CellView({
        grid: grid,
        app: this.app,
        $element: this._createElement(b),
        config: b,
      });
      this.cells.push(cell);
    });

    $win.resize(function(){
      grid.onResize($win.width(), $win.height());
    }).resize();
  }
}
