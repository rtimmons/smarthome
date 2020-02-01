const roomTiles = function({ xPos, roomName, emojiName }) {
    return [
        {
            w: 1,
            h: 1,
            y: 0,
            x: xPos,
            emoji: emojiName,
            activeWhenRoom: roomName,
            onPress: { action: 'ChangeRoom', args: [roomName] },
            onDoublePress: { action: 'AllJoin', args: [roomName] },
        },
        {
            w: 1,
            h: 1,
            y: 1,
            x: xPos,
            emoji: 'Speaker',
            togglesRoom: roomName,
            onPress: { action: 'Music.ToggleRoom', args: [roomName] },
        },
    ];
};

let roomX = 2;

var config = {
    emojis: {
        TV: '📺',
        Film: '🎬',
        Bed: '🛏',
        Rice: '🍙',
        Dog: '🐶',
        Shower: '🛁',
        Earth: '🌍',
        Play: '▶️',
        Pause: '⏸',
        Up: '🔼',
        Down: '🔽',
        MilkyWay: '🌌',
        Klingon: '🖖',
        Skip: '⏭',
        Time15: '🕘',
        Time30: '🕕',
        Nerd: '🤓',
        Notes: '🎶',
        Monkey: '🙉',
        Yell: '🗣',
        Ear: '👂🏽',
        Taco: '🌮',
        Speaker: '🔈',
        News: '📰',
        Sun: '🌕',
        Moon: '🌑',
        Dim: '🌘',
        Sunset: '🌆',
        Check: '✅',
        X: '❌',
        '?': '❓',
        Tulip: '🌷',
        Dancers: '👯',
        Box: '✳️',
        Empty: '⬜️',
        ThumbsUp: '👍🏽',
        ThumbsDown: '👎🏽',
        XMasTree: '🎄',
        Cher: '💁🏻‍♀️',
        Briefcase: '💼',
        Guest: '👨‍👨‍👦',
        Kimono: '👘',
        Sunglasses: '😎',
        Tent: '⛺️',
        BlindUp: '⏫',
        BlindDown: '⏬',
        BlindMid: '⏩'
    },
    rows: 8,
    cols: 11,
    rooms: [
        // This is used by allJoin (double-tap a room).
        // This "should" be implemented in the ExpressAPI
        'Living',
        'Bedroom',
        'Kitchen',
        'Bathroom',
        'Office',
        'Guest Bathroom',
        'Closet',
        'Move',
    ],
    cells: [
        /*
    Only one room can be "active" at a time.
    The Check/?/X below each room is its indicator. These
      indicate if the room that's above it is part of the
      same group as the active room.
    So if all rooms are playing the same thing, clicking
      any of the room icons will leave all the indicators checked.
    Double-click to all join or all leave.
    A room is *always* a part of its own group.


    Click a room to see what's playing in it.
    -> The indicators for the rooms in the same group change
    -> Click the indicator to leave/join the group

    How to silence a room X:
      - click icon for X
      - click its indicator to leave its group

    How to play everywhere:
     - click room you want to duplicate
     - select the unselected indicators

    How to play only in one room X:
     - click icon for X
     - unselect selected indicators

    TODO:
    - icon above volume that matches active room.
      Active => volume controls just that room
      Inactive => volume controls whole group

    */

        ...roomTiles({
            xPos: roomX++,
            emojiName: 'Shower',
            roomName: 'Bathroom',
        }),
        ...roomTiles({
            xPos: roomX++,
            emojiName: 'Kimono',
            roomName: 'Closet',
        }),
        ...roomTiles({ xPos: roomX++, emojiName: 'Tent', roomName: 'Move' }),
        ...roomTiles({ xPos: roomX++, emojiName: 'Bed', roomName: 'Bedroom' }),
        ...roomTiles({ xPos: roomX++, emojiName: 'TV', roomName: 'Living' }),
        ...roomTiles({ xPos: roomX++, emojiName: 'Rice', roomName: 'Kitchen' }),
        ...roomTiles({
            xPos: roomX++,
            emojiName: 'Briefcase',
            roomName: 'Office',
        }),
        ...roomTiles({
            xPos: roomX++,
            emojiName: 'Guest',
            roomName: 'Guest Bathroom',
        }),

        // { w:1, h:1,
        //   y:0, x:7,
        //   emoji: 'Earth',
        //   activeWhenRoom: 'All',
        //   onPress: {action: 'ChangeRoom', args: ['All']},
        // },

        // TODO: display music cover art instead of notes
        {
            w: 1,
            h: 1,
            y: 7,
            x: 0,
            emoji: 'Notes',
            // 'hidden' force-refresh button
            onPress: { action: 'App.Refresh', args: [] },
        },
        {
            w: 9,
            h: 1, // banner
            y: 7,
            x: 1,
            claz: 'state-Music',
            onPress: { action: 'Music.FetchState', args: [] },
        },
        { y: 7, x: 2, w: 0 },
        { y: 7, x: 3, w: 0 },
        { y: 7, x: 4, w: 0 },
        { y: 7, x: 5, w: 0 },
        { y: 7, x: 6, w: 0 },
        { y: 7, x: 7, w: 0 },
        { y: 7, x: 8, w: 0 },
        { y: 7, x: 9, w: 0 },
        // TODO: display music cover art instead of notes
        { w: 1, h: 1, y: 7, x: 10, emoji: 'Notes' },

        { w:1, h:1,
          y:2, x:4,
          emoji: 'BlindUp',
          onPress: {action: 'Blinds.Move', args: ['Up']},
        },
        { w:1, h:1,
          y:2, x:5,
          emoji: 'BlindDown',
          onPress: {action: 'Blinds.Move', args: ['Down']},
        },
        { w:1, h:1,
          y:2, x:6,
          emoji: 'BlindMid',
          onPress: {action: 'Blinds.Move', args: ['Mid']},
        },

        { w:1, h:1,
          y:2, x:8,
          emoji: 'Sun',
          onPress: {action: 'Lights.Scene', args: ['$room','High']},
        },
        { w:1, h:1,
          y:2, x:9,
          emoji: 'Dim',
          onPress: {action: 'Lights.Scene', args: ['$room','Medium']},
        },
        { w:1, h:1,
          y:2, x:10,
          emoji: 'Moon',
          onPress: {action: 'Lights.Scene', args: ['$room','Off']},
        },
        // { w:1, h:1,
        //   y:5, x:8,
        //   emoji: 'Sunset',
        //   onPress: {action: 'Lights.Scene.Savana', args: ["savana"]},
        // },

        // Room/Global volume toggle
        // { w:1, h:1,
        //   y:2, x:1,
        //   emoji: 'Rice',
        //   activeWhenRoom: 'Kitchen',
        // },
        {
            w: 1,
            h: 1,
            y: 3,
            x: 1,
            emoji: 'Up',
            onPress: { action: 'Music.VolumeUp', args: [] },
        },
        {
            w: 1,
            h: 1,
            y: 5,
            x: 1,
            emoji: 'Down',
            onPress: { action: 'Music.VolumeDown', args: [] },
        },
        {
            w: 1,
            h: 1,
            y: 4,
            x: 1,
            emoji: 'Klingon',
            onPress: { action: 'Music.VolumeSame', args: [] },
        },

        ////
        // volume "slider"
        ////
        // TODO: in column 0, have volume absolute numbers. Bottom is mute.
        //       The number of "lit up" rows corresponds to the volume
        //       of the current group associated with active room. Click once
        //       to change for the active room; double click to change for
        //       whole group.
        //
        // TODO: 0 is top of screen, so volumeLevel vals
        //       need to be reversed (volumeLevel = 6 - y)
        // { w:1, h:1,
        //   y:6, x:0,
        //   emoji: 'Monkey',
        //   volumeLevel: 6,
        // },
        // { w:1, h:1,
        //   y:5, x:0,
        //   emoji: 'Box',
        //   volumeLevel: 5,
        // },
        // { w:1, h:1,
        //   y:4, x:0,
        //   emoji: 'Box',
        //   volumeLevel: 4,
        // },
        // { w:1, h:1,
        //   y:3, x:0,
        //   emoji: 'Empty',
        //   volumeLevel: 3,
        // },
        // { w:1, h:1,
        //   y:2, x:0,
        //   emoji: 'Empty',
        //   volumeLevel: 2,
        // },
        // { w:1, h:1,
        //   y:1, x:0,
        //   emoji: 'Empty',
        //   volumeLevel: 1,
        // },
        // { w:1, h:1,
        //   y:0, x:0,
        //   emoji: 'Empty',
        //   volumeLevel: 0,
        // },
        ////

        /////
        // Presets
        /////
        {
            w: 1,
            h: 1,
            y: 4,
            x: 3,
            emoji: 'News',
            onPress: { action: 'Music.Favorite', args: ['Play NPR One'] },
        },
        {
            w: 1,
            h: 1,
            y: 4,
            x: 5,
            emoji: 'Tulip',
            onPress: { action: 'Music.Favorite', args: ['Tulip Radio'] },
        },
        {
            w: 1,
            h: 1,
            y: 3,
            x: 6,
            emoji: 'Monkey',
            onPress: { action: 'Music.Favorite', args: ['Sosononos'] },
        },
        {
            w: 1,
            h: 1,
            y: 3,
            x: 7,
            emoji: 'Nerd',
            onPress: {
                action: 'Music.Favorite',
                args: ['Alpha Chill - Medium'],
            },
        },
        {
            w: 1,
            h: 1,
            y: 4,
            x: 7,
            emoji: 'Sunglasses',
            onPress: { action: 'Music.Favorite', args: ['Office DJ'] },
        },

        // { w:1, h:1,
        //   y:4, x:8,
        //   emoji: 'XMasTree',
        //   onPress: {action: 'Music.Favorite', args: ['Vince Guaraldi Trio (Holiday) Radio']},
        // },
        {
            w: 1,
            h: 1,
            y: 3,
            x: 8,
            emoji: 'Cher',
            onPress: { action: 'Music.Favorite', args: ['Cher Essentials'] },
        },
        {
            w: 1,
            h: 1,
            y: 4,
            x: 8,
            emoji: 'MilkyWay',
            onPress: { action: 'Music.Favorite', args: ['Zero 7 Radio'] },
        },
        {
            w: 1,
            h: 1,
            y: 3,
            x: 9,
            emoji: 'Dog',
            onPress: { action: 'Music.Favorite', args: ['Frankie'] },
        },
        {
            w: 1,
            h: 1,
            y: 4,
            x: 6,
            emoji: 'Dancers',
            onPress: {
                action: 'Music.Favorite',
                args: ['Britney Spears Radio'],
            },
        },
        // TODO: maybe just use built-in pandora support?
        {
            w: 1,
            h: 1,
            y: 3,
            x: 5,
            emoji: 'Taco',
            onPress: {
                action: 'Music.Favorite',
                args: ['Despacito (Feat. Daddy Yankee) Radio'],
            },
        },
        {
            w: 1,
            h: 1,
            y: 3,
            x: 3,
            emoji: 'Film',
            onPress: { action: 'Music.Preset', args: ['$room-tv'] },
        },

        ////
        // Pandora ThumbsUp/ThumbsDown
        //
        // TODO: implement
        // { w:1, h:1,
        //   y:6, x:3,
        //   emoji: 'ThumbsUp',
        // },
        // { w:1, h:1,
        //   y:6, x:6,
        //   emoji: 'ThumbsDown',
        // },

        // TODO: toggle play/pause icon
        {
            w: 1,
            h: 1,
            y: 6,
            x: 3,
            emoji: 'Play',
            onPress: { action: 'Music.PlayPause', args: [] },
        },
        {
            w: 1,
            h: 1,
            y: 6,
            x: 5,
            emoji: 'Pause',
            onPress: { action: 'Music.Pause', args: [] },
        },
        {
            w: 1,
            h: 1,
            y: 6,
            x: 7,
            emoji: 'Skip',
            onPress: { action: 'Music.Next', args: [] },
        },

        // TODO: sleep timer buttons - sonos http API has it built in
    ],
    poll: [{ action: 'Music.FetchState', args: [], period: 2000 }],
};
