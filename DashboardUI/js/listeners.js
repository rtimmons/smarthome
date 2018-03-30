class ActiveCells {
  onMessage(e) {
    if (e.Name != 'Room.Changed') {
      return;
    }

    e.app.eachCell(cell => {
      cell.setActive(
        cell.isActiveForRoom(e.ToRoom)
      );
    });
  }
}

class FetchStateOnRoomChange {
  onMessage(e) {
    if (e.Name != 'Room.Changed') {
      return;
    }
    e.app.fetchState();
  }
}

class RoomSaver {
  onMessage(e) {

    if (e.Name == 'App.Initialized') {
      var room = window.cookies.get('Room') || 'Kitchen';
      e.app.changeRoom(room);
    }

    if (e.Name != 'Room.Changed') {
      return;
    }

    window.cookies.set('Room', e.ToRoom);
  }
}

class BackgroundChanger {
  onMessage(e) {
    if (e.Name != 'Room.StateObserved') {
      return;
    }

    var track = e.State.currentTrack;

    var artUrl = track.absoluteAlbumArtUri || track.albumArtUri;
    e.app.setBackgroundImage(artUrl);

    var title = track.title;
    e.app.setBanner(title);
  }
}

class ZoneUpdater {
  simplify(zones) {
    return zones.map(zone => {
      return {
        members: zone.members.map(m => m.roomName)
      };
    });
  }

  onMessage(e) {
    if (e.Name != 'Room.ZonesObserved') {
      return;
    }
    var zones = this.simplify(e.Zones);
    e.app.updateZones(zones);
  }
}

class GenericOnPress {
  onMessage(e) {
    if (e.Name != 'Cell.Press') {
      return;
    }

    var onPress = e.Cell.config.onPress;
    if (!onPress) {
      return;
    }

    var action = onPress.action;
    var args   = onPress.args;
    e.app.onAction(action, args, e);
  }
}

class GenericOnDoublePress {
  onMessage(e) {
    if (e.Name != 'Cell.DoublePress') {
      return;
    }

    var onPress = e.Cell.config.onDoublePress;
    if (!onPress) {
      return;
    }

    var action = onPress.action;
    var args   = onPress.args;
    e.app.onAction(action, args, e);
  }
}
