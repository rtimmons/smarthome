var config = {
  Rooms: [
    'Bathroom',
    'Bedroom',
    'Kitchen',
    'Living'
  ],

  Actions: [
    'Music.Join',
    'Music.VolumeUp',
    'Music.VolumeDown',
    'Music.Mute',

    'Music.Resume',
    'Music.Pause',
    'Music.Skip',
    'Music.ThumbsUp',
    'Music.ThumbsDown',

    'Music.PlayDespacito',
    'Music.PlayNPR',
    'Music.PlayMusic',

    'Light.On',
    'Light.Dim',
    'Light.Off',
    'Light.Scene1',
  ]
};

// Main
$(() => {
  new App(window.location.href, $('#ui')).run()
});