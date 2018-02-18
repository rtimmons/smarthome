// fastclick hook
$(() => {
  FastClick.attach(document.body);
});

// app.js hook
$(() => {
  var container = $('#grid');

  var grid = new GridView({
    container:  container,
    config:     config,
  });

  var app = new App({
    window:    window,
    container: container,
    grid:      grid,
    config:    config,
    secret:    secret,
  });

  app.subscribe(new BackgroundChanger());
  app.subscribe(new ActiveCells());
  app.subscribe(new GenericOnPress());
  app.subscribe(new GenericOnDoublePress());
  app.subscribe(new FetchStateOnRoomChange());
  app.subscribe(new ZoneUpdater());
  app.subscribe(new EmojiState());

  app.run()

  window.app = app;
});
