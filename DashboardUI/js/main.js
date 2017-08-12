'use strict';

// fastclick hook
$(function () {
  FastClick.attach(document.body);
});

// app.js hook
$(function () {
  var container = $('#grid');

  var grid = new Grid({
    container: container,
    config: config
  });

  var app = new App({
    window: window,
    container: container,
    grid: grid,
    config: config
  });

  app.run();
});