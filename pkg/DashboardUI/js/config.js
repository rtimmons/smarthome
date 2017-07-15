
var config = {
  emojis: {
      'TV':       '📺' ,
      'Bed':      '🛏'  ,
      'Rice':     '🍙' ,
      'Shower':   '🛀' ,
      'Earth':    '🌍' ,
      'Play':     '▶️',
      'Up':       '🔼' ,
      'Down':     '🔽' ,
      'Notes':    '🎶',
      'Monkey':   '🙉',
      'Yell':     '🗣',
      'Ear':      '👂🏽',
      'Taco':     '🌮',
      'News':     '📰',
      'Sun':      '🌕',
      'Moon':     '🌑',
      'Dim':      '🌘',
      'Sunset':   '🌆',
  },
  rows: 9,
  cols: 12,
  rooms: [
    'Living',
    'Bedroom',
    'Kitchen',
    'Bathroom',
  ],
  cells: [
    { w:1, h:1,
      y:0, x:3,
      icon: 'TV',
      // TODO: rename onPress to onClick, onDblPress to onDblClick
      activeWhenRoom: 'Living',
      onPress: {action: 'ChangeRoom', args: ['Living']},
      onDblPress: {action: 'AllJoin', args: ['Living']},
    },
    { w:1, h:1,
      y:0, x:4,
      icon: 'Bed',
      activeWhenRoom: 'Bedroom',
      onPress: {action: 'ChangeRoom', args: ['Bedroom']},
      onDblPress: {action: 'AllJoin', args: ['Bedroom']},
    },
    { w:1, h:1,
      y:0, x:5,
      icon: 'Rice',
      activeWhenRoom: 'Kitchen',
      onPress: {action: 'ChangeRoom', args: ['Kitchen']},
      onDblPress: {action: 'AllJoin', args: ['Kitchen']},
    },
    { w:1, h:1,
      y:0, x:6,
      icon: 'Shower',
      activeWhenRoom: 'Bathroom',
      onPress: {action: 'ChangeRoom', args: ['Bathroom']},
      onDblPress: {action: 'AllJoin', args: ['Bathroom']},
    },

    // { w:1, h:1,
    //   y:0, x:7,
    //   icon: 'Earth',
    //   activeWhenRoom: 'All',
    //   onPress: {action: 'ChangeRoom', args: ['All']},
    // },

    { w:1, h:1,
      y:7, x:0,
      icon: 'Notes'
    },
    { w:10, h:1,
      y:7, x:1,
      claz: 'state-Music',
      onPress: {action: 'Music.GetState', args: []},
    },
    { y:7, x:2, w:0 },
    { y:7, x:3, w:0 },
    { y:7, x:4, w:0 },
    { y:7, x:5, w:0 },
    { y:7, x:6, w:0 },
    { y:7, x:7, w:0 },
    { y:7, x:8, w:0 },
    { y:7, x:9, w:0 },
    { y:7, x:10, w:0 },

    { w:1, h:1,
      y:7, x:11,
      icon: 'Notes'
    },


    { w:1, h:1,
      y:3, x:6,
      icon: 'Sun',
      onPress: {action: 'Lights.On', args: []},
    },
    { w:1, h:1,
      y:4, x:6,
      icon: 'Dim',
      onPress: {action: 'Lights.Scene.Dim', args: []},
    },
    { w:1, h:1,
      y:5, x:6,
      icon: 'Moon',
      onPress: {action: 'Lights.Off', args: []},
    },
    { w:1, h:1,
      y:6, x:6,
      icon: 'Sunset',
      onPress: {action: 'Lights.Scene.Savana', args: ["savana"]},
    },
    { w:1, h:1,
      y:4, x:1,
      icon: 'Up',
      onPress: {action: 'Music.VolumeUp', args: []},
    },
    { w:1, h:1,
      y:5, x:1,
      icon: 'Down',
      onPress: {action: 'Music.VolumeDown', args: []},
    },
    { w:1, h:1,
      y:5, x:2,
      icon: 'News',
      onPress: {action: 'Music.Preset', args: ['playnpr']},
    },
    { w:1, h:1,
      y:4, x:2,
      icon: 'Taco',
      onPress: {action: 'Music.Preset', args: ['radio.despacito']},
    },
    { w:1, h:1,
      y:8, x:1,
      icon: 'Play',
      onPress: {action: 'Music.PlayPause', args: []},
    },
  ],
  poll: [
    {action: 'Music.GetState', args: [], period: 3000},
    // refresh every 15 seconds
    {action: 'App.Refresh', args: [], period: 15000},
  ]
};