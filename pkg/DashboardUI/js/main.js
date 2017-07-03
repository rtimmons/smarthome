$(() => {
  var $h = $('#grid');
  var emojis = {
    'TV':       '📺' ,
    'Bed':      '🛏'  ,
    'Rice':     '🍚' ,
    'Toilet':   '🚽' ,
    'Earth':    '🌍' ,
    'Up':       '🔼' ,
    'Down':     '🔽' ,
  };
  
  var buttons = [
    [0, 2, 'TV',      'ChangeRoom', ['Living']],
    [0, 3, 'Bed',     'ChangeRoom', ['Bedroom']],
    [0, 4, 'Rice',    'ChangeRoom', ['Kitchen']],
    [0, 5, 'Toilet',  'ChangeRoom', ['Bathroom']],

    [0, 7, 'Earth',  'ChangeRoom', ['All']],
    

    [4, 1, 'Up',      'Music.VolumeUp',   []],
    [5, 1, 'Down',    'Music.VolumeDown', []],
  ];

  var app = new App($h);
  app.configure({
    // TODO: rows/cols in here
    // TODO: grid.js into app
    emojis: emojis,
    buttons: buttons,
  })
});