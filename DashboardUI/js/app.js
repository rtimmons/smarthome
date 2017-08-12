'use strict';

var _createClass = function () { function defineProperties(target, props) { for (var i = 0; i < props.length; i++) { var descriptor = props[i]; descriptor.enumerable = descriptor.enumerable || false; descriptor.configurable = true; if ("value" in descriptor) descriptor.writable = true; Object.defineProperty(target, descriptor.key, descriptor); } } return function (Constructor, protoProps, staticProps) { if (protoProps) defineProperties(Constructor.prototype, protoProps); if (staticProps) defineProperties(Constructor, staticProps); return Constructor; }; }();

function _classCallCheck(instance, Constructor) { if (!(instance instanceof Constructor)) { throw new TypeError("Cannot call a class as a function"); } }

var log = console.log;

var App = function () {
  function App(args) {
    _classCallCheck(this, App);

    this.window = args.window;
    this.$ = args.container;
    this.grid = args.grid;
    this.config = args.config;
    this.rooms = args.config.rooms;
    this.listeners = {};
  }

  _createClass(App, [{
    key: 'submit',
    value: function submit(topic, event) {
      (this.listeners[topic] || []).forEach(function (l) {
        return l(event);
      });
    }
  }, {
    key: 'listen',
    value: function listen(topic, callback) {
      this.listeners[topic] = this.listeners[topic] || [];
      this.listeners[topic].push(callback);
    }
  }, {
    key: 'run',
    value: function run() {
      var _this = this;

      this.grid.init($(this.window));
      this.config.cells.forEach(function (b) {
        var cell = _this.grid.cell(b);
        cell.data('config', b);
        cell.html(_this.config.emojis[b.icon]);
        cell.addClass(b.claz);

        var tapped = false;
        var app = _this;
        // hacky thing to bind double-tap
        cell.on("touchstart", function (e) {
          if (!tapped) {
            tapped = setTimeout(function () {
              tapped = null;
              cell.click();
            }, 300);
          } else {
            clearTimeout(tapped);
            tapped = null;
            cell.dblclick();
          }
          e.preventDefault();
        });

        cell.click(function () {
          return _this.submit('Cell.Click', { Cell: cell });
        });
        cell.dblclick(function () {
          return _this.submit('Cell.Dblclick', { Cell: cell });
        });
        cell.on('doubletap', function () {
          return _this.submit('Cell.Dblclick', { Cell: cell });
        });
      });

      this.config.poll.forEach(function (p) {
        var f = function f() {
          return _this.onAction(p.action, p.args);
        };
        setInterval(f, p.period);
      });

      this.listen('Cell.Click', function (e) {
        var b = e.Cell.data('config');
        if (b && b.onPress) {
          _this.onAction(b.onPress.action, b.onPress.args);
        }
      });

      this.listen('Cell.Dblclick', function (e) {
        var d = e.Cell.data('config');
        if (d && d.onDblPress) {
          _this.onAction(d.onDblPress.action, d.onDblPress.args);
        }
      });

      this.listen('Room.StateObserved', function (e) {
        var track = e.State.currentTrack;
        var artUrl = track.absoluteAlbumArtUri || track.albumArtUri;
        if (artUrl) {
          $('body').css({ backgroundImage: 'url("' + artUrl + '")' });
        } else {
          $('body').css({ backgroundImage: '' });
        }
        var title = track.title;
        _this.$.find('.state-Music').html(title ? title.substr(0, 19) : '');
      });

      this.listen('Room.Changed', function (e) {
        _this.grid.allCells().forEach(function (c) {
          var d = c.data('config');
          if (d && d.activeWhenRoom) {
            if (e.ToRoom == d.activeWhenRoom) {
              c.addClass('active');
            } else {
              c.removeClass('active');
            }
          }
        });
      });
      this.listen('Room.Changed', function (e) {
        _this.getState();
      });

      this.listen('App.Started', function (e) {
        _this.changeRoom('Kitchen');
      });

      this.listen('App.Started', function (e) {
        _this.reindex();
      });

      this.submit('App.Started', {});
    }
  }, {
    key: 'allJoin',
    value: function allJoin(room) {
      var _this2 = this;

      // TODO: could be more clever about getting all room names from `/zones`
      // it's in .members.roomName
      log('allJoin ' + room);
      var delay = 0;
      this.config.rooms.filter(function (x) {
        return x != room;
      }).forEach(function (other) {
        setTimeout(function () {
          return _this2.request('http://retropie.local:5005/' + other + '/join/' + room);
        }, delay);
        delay += 1000; // only 1 request/second
      });
    }
  }, {
    key: 'reindex',
    value: function reindex() {
      this.request('http://retropie.local:5005/reindex');
    }
  }, {
    key: 'refresh',
    value: function refresh() {
      window.location.reload();
    }
  }, {
    key: 'changeRoom',
    value: function changeRoom(toRoom) {
      var oldRoom = this.room;
      this.room = toRoom;
      this.submit('Room.Changed', { FromRoom: oldRoom, ToRoom: toRoom });
    }
  }, {
    key: 'request',
    value: function request(url) {
      if (window.location.href.match(/.*debug.*/)) {
        alert('fake request ' + url);
        return {};
      }
      return $.ajax(url).fail(function (err) {
        return console.log(url, err);
      });
    }
  }, {
    key: 'getState',
    value: function getState() {
      var _this3 = this;

      $.ajax('http://retropie.local:5005/' + this.room + '/state').done(function (resp) {
        _this3.submit('Room.StateObserved', {
          State: resp
        });
      });
    }
  }, {
    key: 'onAction',
    value: function onAction(action, params) {

      switch (action) {
        case 'AllJoin':
          this.allJoin.apply(this, params);
          break;
        case 'ChangeRoom':
          this.changeRoom.apply(this, params);
          break;
        case 'Music.GetState':
          this.getState();
          break;
        case 'Lights.On':
          this.request('http://maker.ifttt.com/trigger/' + this.room + '_scene_bright/with/key/cLNpbWpb3jYP550-Mna27W');
          this.request('http://maker.ifttt.com/trigger/' + this.room + '_switch_on/with/key/cLNpbWpb3jYP550-Mna27W');
          // this.request('http://retropie:5005/' + this.room + '/say/on/en-gb')
          break;
        case 'Lights.Scene.Dim':
          this.request('http://maker.ifttt.com/trigger/' + this.room + '_scene_dim/with/key/cLNpbWpb3jYP550-Mna27W');
          this.request('http://maker.ifttt.com/trigger/' + this.room + '_switch_off/with/key/cLNpbWpb3jYP550-Mna27W');
          // this.request('http://retropie:5005/' + this.room + '/say/dimmed/en-gb')
          break;
        case 'Lights.Off':
          this.request('http://maker.ifttt.com/trigger/' + this.room + '_off/with/key/cLNpbWpb3jYP550-Mna27W');
          this.request('http://maker.ifttt.com/trigger/' + this.room + '_switch_off/with/key/cLNpbWpb3jYP550-Mna27W');
          // this.request('http://retropie:5005/' + this.room + '/say/off/en-gb')
          break;
        case 'Lights.Scene.Savana':
          this.request('http://maker.ifttt.com/trigger/' + this.room + '_scene_savanna/with/key/cLNpbWpb3jYP550-Mna27W');
          this.request('http://maker.ifttt.com/trigger/' + this.room + '_switch_off/with/key/cLNpbWpb3jYP550-Mna27W');
          // this.request('http://retropie:5005/' + this.room + '/say/savanna/en-gb')
          break;
        case 'Music.PlayPause':
          this.request('http://retropie.local:5005/' + this.room + '/playpause');
          break;
        case 'Music.Preset':
          this.request('http://retropie.local:5005/' + this.room + '/preset/' + params[0]);
          break;
        case 'Music.VolumeUp':
          this.request('http://retropie.local:5005/' + this.room + '/volume/+5');
          break;
        case 'Music.VolumeDown':
          this.request('http://retropie.local:5005/' + this.room + '/volume/-5');
          break;
        case 'Music.Next':
          this.request('http://retropie.local:5005/' + this.room + '/next');
          break;
        case 'App.Refresh':
          this.refresh();
          break;
      }
    }
  }]);

  return App;
}();