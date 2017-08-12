'use strict';

var _createClass = function () { function defineProperties(target, props) { for (var i = 0; i < props.length; i++) { var descriptor = props[i]; descriptor.enumerable = descriptor.enumerable || false; descriptor.configurable = true; if ("value" in descriptor) descriptor.writable = true; Object.defineProperty(target, descriptor.key, descriptor); } } return function (Constructor, protoProps, staticProps) { if (protoProps) defineProperties(Constructor.prototype, protoProps); if (staticProps) defineProperties(Constructor, staticProps); return Constructor; }; }();

function _classCallCheck(instance, Constructor) { if (!(instance instanceof Constructor)) { throw new TypeError("Cannot call a class as a function"); } }

var Grid = function () {
  function Grid(args) {
    _classCallCheck(this, Grid);

    this.$element = args.container;
    var config = args.config;

    this.cells = [];
    this.cols = config.cols;
    this.rows = config.rows;
  }

  _createClass(Grid, [{
    key: 'onResize',
    value: function onResize(width, height) {
      var square = Math.min(width / this.cols, height / this.rows);
      this.square = square;
      $('.cell').each(function () {
        var t = $(this);
        t.css({
          height: (t.attr('rowspan') || 1) * square + 'px',
          width: (t.attr('colspan') || 1) * square + 'px',
          fontSize: square * 2 / 3 + 'px',
          lineHeight: square + 'px'
        });
      });

      this.$element.width((square + 2) * this.cols);
    }
  }, {
    key: 'allCells',
    value: function allCells() {
      return this.cells;
    }
  }, {
    key: 'cell',
    value: function cell(size) {
      var cell = this.$element.find('#cell-' + size.y + '-' + size.x);

      if (size.w == 0 || size.h == 0) {
        cell.remove();
      } else {
        cell.attr('colspan', size.w);
      }

      this.cells.push(cell);
      return cell;
    }
  }, {
    key: 'init',
    value: function init($win) {
      var grid = this;

      for (var row = 0; row < this.rows; row++) {
        var tr = $('<tr>');
        for (var col = 0; col < this.cols; col++) {
          var cell = $('<td class="cell">');
          cell.addClass('row-' + row);
          cell.addClass('col-' + col);
          cell.attr('id', 'cell-' + row + '-' + col);
          tr.append(cell);
          this.cells.push(cell);
        }
        this.$element.append(tr);
      }

      $win.resize(function () {
        grid.onResize($win.width(), $win.height());
      }).resize();
    }
  }]);

  return Grid;
}();