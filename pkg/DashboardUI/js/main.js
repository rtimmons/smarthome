$(() => {
  var container = $('#grid');

  var grid = new Grid({
    container:  container,
    config:     config,
  });

  var app = new App({
    window:    window,
    container: container,
    grid:      grid,
    config:    config
  });

  app.run()
});