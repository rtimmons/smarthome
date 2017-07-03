$(function(){
  var cols = 12;
  var rows = 9;
  var win = $(window);

  var grid = $('#grid');
  for(var row=0; row<rows; row++) {
    for(var col=0; col<cols; col++) {
      var cell = $('<div class="cell">');
      cell.addClass('row-'+row);
      cell.addClass('col-'+col);
      cell.attr('id', 'cell-'+row+'-'+col);
      grid.append(cell);
    }
  }

  var onResize = function() {
    var width = win.width();
    var height = win.height();

    var square = Math.min(width/cols, height/rows);
    $('.cell').css({
      height: square,
      width: square,
    });

    $('#grid').width((square + 2) * cols);
  };

  win.resize(onResize);
  onResize();
});

