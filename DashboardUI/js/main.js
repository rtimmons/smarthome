// fastclick hook
$(() => {
  FastClick.attach(document.body);
});

// app.js hook
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
    config:    config,
    secret:    secret,
  });

  app.run()
});