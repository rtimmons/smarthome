// fastclick hook
$(() => {
  FastClick.attach(document.body);
});

// app.js hook
$(() => {
  var container = $('#grid');

  var pubsub = new PubSub();

  var grid = new GridView({
    container:  container,
    config:     config,
    pubsub:     pubsub,
  });

  var app = new App({
    window:    window,
    pubsub:    pubsub,
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
  app.subscribe(new RoomSaver());

  app.run()

  window.app = app;
});
