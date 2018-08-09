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

  pubsub.subscribe('*', new ChangeBodyClassOnTime());
  pubsub.subscribe('Room.StateObserved',  new BackgroundChanger());
  pubsub.subscribe('Room.Changed',        new ActiveCells());
  pubsub.subscribe('Cell.Press',          new GenericOnPress());
  pubsub.subscribe('Cell.DoublePress',    new GenericOnDoublePress());
  pubsub.subscribe('Room.Changed',        new FetchStateOnRoomChange());
  pubsub.subscribe('Room.ZonesObserved',  new ZoneUpdater());
  pubsub.subscribe(['App.Initialized', 'Room.Changed'], new RoomSaver());

  app.run()

  window.app = app;
});
