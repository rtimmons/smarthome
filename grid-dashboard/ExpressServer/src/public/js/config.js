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

const buildCells = function(rows, cols, cells) {
    const cellMap = {};
    cells.forEach(cell => {
        if (cell.x === undefined || cell.y === undefined) {
            throw new Error('Base cell missing x/y coordinate.');
        }
        if (cell.x < 0 || cell.x >= cols || cell.y < 0 || cell.y >= rows) {
            throw new Error(
                'Base cell at (' +
                    cell.x +
                    ',' +
                    cell.y +
                    ') is outside the grid.'
            );
        }
        const key = cell.y + ':' + cell.x;
        if (cellMap[key]) {
            throw new Error(
                'Duplicate base cell at (' + cell.x + ',' + cell.y + ').'
            );
        }
        cellMap[key] = cell;
    });

    const allCells = [];
    for (let y = 0; y < rows; y++) {
        for (let x = 0; x < cols; x++) {
            const key = y + ':' + x;
            if (cellMap[key]) {
                allCells.push(cellMap[key]);
            } else {
                allCells.push({ w: 1, h: 1, x: x, y: y });
            }
        }
    }
    return allCells;
};

const ledGridButtons = function(yPos) {
    return [
        {
            x: 6,
            y: yPos,
            emoji: 'Rainbow',
            onPress: { action: 'LedGrid.Start', args: ['rainbow'] },
        },
        {
            x: 7,
            y: yPos,
            emoji: 'Sparkles',
            onPress: { action: 'LedGrid.Start', args: ['sparkle'] },
        },
        {
            x: 8,
            y: yPos,
            emoji: 'Tetris',
            onPress: { action: 'LedGrid.Start', args: ['tetris'] },
        },
    ];
};

const rows = 8;
const cols = 11;

let roomX = 1;

const config = {
    emojis: {
        Banjo: '🪕',
        TV: '📺',
        Film: '🎬',
        Bed: '🛏',
        Rice: '🍙',
        Dog: '🐶',
        Chair: '🪑',
        Shower: '🛁',
        Boat: '⛵️',
        Earth: '🌍',
        Play: '▶️',
        Pause: '⏸',
        Up: '🔼',
        Down: '🔽',
        MilkyWay: '🌌', // 🎷
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
        Calendar: '📅',
        News: '📰',
        Sun: '🌕',
        Moon: '🌑',
        Dim: '🌘',
        Sunset: '🌆',
        Check: '✅',
        Chill: '🥶', // 🎷
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
        Grande: '👸🏻',
        Briefcase: '💼',
        Guest: '👨‍👨‍👦',
        Kimono: '👘',
        Sunglasses: '😎',
        Tent: '⛺️',
        DoubleUp: '⏫',
        DoubleDown: '⏬',
        DoubleRight: '⏩',
        SingleUp: '⬆',
        SingleDown: '⬇',
        SteveAoki: '💇🏻‍♂️',
        Robot: '🦾',
        Rainbow: '🌈',
        Sparkles: '✨',
        Tetris: '🧱',
    },
    rows: rows,
    cols: cols,
    printerPort: 8099,
    rooms: [
        // This is used by allJoin (double-tap a room).
        // This "should" be implemented in the ExpressAPI
        'Living Room',
        'Bedroom',
        'Kitchen',
        'Bathroom',
        'Office',
        'Guest Bathroom',
        'Closet',
        'Move',
    ],
    cells: buildCells(rows, cols, [
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

        ...roomTiles({ xPos: roomX++, emojiName: 'Shower',    roomName: 'Bathroom' }),
        ...roomTiles({ xPos: roomX++, emojiName: 'Kimono',    roomName: 'Closet' }),
        ...roomTiles({ xPos: roomX++, emojiName: 'Bed',       roomName: 'Bedroom' }),
        ...roomTiles({ xPos: roomX++, emojiName: 'Tent',      roomName: 'Move' }),
        ...roomTiles({ xPos: roomX++, emojiName: 'Rice',      roomName: 'Kitchen' }),
        ...roomTiles({ xPos: roomX++, emojiName: 'TV',        roomName: 'Living Room' }),
        ...roomTiles({ xPos: roomX++, emojiName: 'Guest',     roomName: 'Guest Bathroom' }),
        ...roomTiles({ xPos: roomX++, emojiName: 'Briefcase', roomName: 'Office' }),

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
        { w: 1, h: 1, y: 7, x: 10, emoji: 'Notes' },

        { w:1, h:1,
            y:2, x:2,
            emoji: 'SingleUp',
            onPress: {action: 'Blinds.Move', args: ['Roller','Up']},
        },
        { w:1, h:1,
            y:2, x:3,
            emoji: 'SingleDown',
            onPress: {action: 'Blinds.Move', args: ['Roller','Down']},
        },
        { w:1, h:1,
            y:2, x:4,
            emoji: 'DoubleUp',
            onPress: {action: 'Blinds.Move', args: ['Blackout','Up']},
        },
        { w:1, h:1,
            y:2, x:5,
            emoji: 'DoubleDown',
            onPress: {action: 'Blinds.Move', args: ['Blackout','Down']},
        },
        // { w:1, h:1,
        //     y:2, x:6,
        //     emoji: 'DoubleRight',
        //     onPress: {action: 'Blinds.Move', args: ['Blackout','Mid']},
        // },

        { w:1, h:1,
            y:2, x:7,
            emoji: 'Sun',
            onPress: {action: 'Lights.Scene', args: ['$room','High']},
        },
        { w:1, h:1,
            y:2, x:8,
            emoji: 'Dim',
            onPress: {action: 'Lights.Scene', args: ['$room','Medium']},
        },
        { w:1, h:1,
            y:2, x:9,
            emoji: 'Moon',
            onPress: {action: 'Lights.Scene', args: ['$room','Off']},
            onDoublePress: {action: 'Lights.Scene', args: ['all','off']},
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
            onDoublePress: { action: 'Music.SetVolume', args: [10] },
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
        // {
        //     w: 1,
        //     h: 1,
        //     y: 4,
        //     x: 3,
        //     emoji: 'News',
        //     onPress: {  action: 'Music.Favorite', args: ['Play NPR One'] },
        // },
        {
            w: 1,
            h: 1,
            y: 4,
            x: 5,
            emoji: 'Boat',
            onPress: { action: 'Music.Favorite', args: ['Rockboat'] },
        },
        {
            w: 1,
            h: 1,
            y: 4,
            x: 5+4-1,
            emoji: 'SteveAoki',
            onPress: { action: 'Music.Favorite', args: ['735 - Steve Aoki\'s Remix Radio'] },
        },
        // {
        //     w: 1,
        //     h: 1,
        //     y: 3,
        //     x: 5+4-1,
        //     emoji: 'Monkey',
        //     onPress: { action: 'Music.Favorite', args: ['Sosononos'] },
        // },
        {
            w: 1,
            h: 1,
            y: 4,
            x: 7-1,
            emoji: 'Sunglasses',
            onPress: { action: 'Music.Favorite', args: ['Office DJ'] },
        },
        {
            w: 1,
            h: 1,
            y: 5,
            x: 6,
            emoji: null,
            onPress: null,
        },
        {
            w: 1,
            h: 1,
            y: 5,
            x: 7,
            emoji: null,
            onPress: null,
        },
        {
            w: 1,
            h: 1,
            y: 4-1,
            x: 7-1,
            emoji: 'Banjo',
            onPress: { action: 'Music.Favorite', args: ['Carbon Leaf'] },
        },
        // { w:1, h:1,
        //   y:4, x:8,
        //   emoji: 'XMasTree',
        //   onPress: {action: 'Music.Favorite', args: ['Vince Guaraldi Trio (Holiday) Radio']},
        // },
        // {
        //     w: 1,
        //     h: 1,
        //     y: 3,
        //     x: 8,
        //     emoji: 'Cher',
        //     onPress: { action: 'Music.Favorite', args: ['Cher Essentials'] },
        // },
        {
            w: 1,
            h: 1,
            y: 4,
            x: 8-1,
            emoji: 'MilkyWay',
            onPress: { action: 'Music.Favorite', args: ['Zero 7'] },
        },
        {
            w: 1,
            h: 1,
            y: 5,
            x: 8,
            emoji: null,
            onPress: null,
        },
        // {
        //     w: 1,
        //     h: 1,
        //     y: 3,
        //     x: 9,
        //     emoji: 'Grande',
        //     onPress: { action: 'Music.Favorite', args: ['Ariana Grande Essentials'] },
        // },
        {
            w: 1,
            h: 1,
            y: 4-1,
            x: 9-1-1,
            emoji: 'Chill',
            onPress: { action: 'Music.Favorite', args: ['53 - SiriusXM Chill'] },
        },
        // {
        //     w: 1,
        //     h: 1,
        //     y: 4,
        //     x: 6,
        //     emoji: 'Dancers',
        //     onPress: {
        //         action: 'Music.Favorite',
        //         args: ['Britney Spears Essentials'],
        //     },
        // },
        // TODO: maybe just use built-in pandora support?
        // {
        //     w: 1,
        //     h: 1,
        //     y: 3,
        //     x: 5,
        //     emoji: 'Taco',
        //     onPress: {
        //         action: 'Music.Favorite',
        //         args: ['Despacito (Feat. Daddy Yankee) Radio'],
        //     },
        // },
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
    ]),
    roomOverrides: {
        // Example overrides:
        // Office: {
        //     cells: [
        //         { x: 6, y: 4, emoji: null, onPress: null },
        //     ],
        // },
        // 'Living Room': {
        //     cells: [
        //         {
        //             x: 6,
        //             y: 2,
        //             emoji: 'TV',
        //             onPress: { action: 'Music.Preset', args: ['living-room-tv'] },
        //         },
        //     ],
        // },
        'Living Room': {
            cells: [
                ...ledGridButtons(5),
            ],
        },
        Kitchen: {
            cells: [
                ...ledGridButtons(5),
                {
                    x: 10,
                    y: 2,
                    emoji: 'Calendar',
                    onPress: { action: 'Printer.Preset', args: ['S3nysytjA14'] },
                },
            ],
        },
    },
    poll: [{ action: 'Music.FetchState', args: [], period: 2000 }],
};
