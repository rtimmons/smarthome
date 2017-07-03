$(function(){
  // TODO: max rows/cols based on config
  var cols = config.cols;
  var rows = config.rows;
  var win = $(window);

  var grid = $('#grid');
  for(var row=0; row<rows; row++) {
    for(var col=0; col<cols; col++) {
      var cell = $('<div class="cell">');
      cell.addClass('row-'+row);
      cell.addClass('col-'+col);
      cell.attr('id', 'cell-'+row+'-'+col);
      grid.append(cell);
      cell.dblclick(function() { console.log($(this).attr('id')) });
    }
  }

  var onResize = function() {
    var width = win.width();
    var height = win.height();

    var square = Math.min(width/cols, height/rows);
    $('.cell').css({
      height: (square) + 'px',
      width: (square) + 'px',
      fontSize: (square * 2 / 3) + 'px',
      lineHeight: (square) + 'px',
    });

    $('#grid').width((square + 2) * cols);
  };

  win.resize(onResize);
  onResize();
});

