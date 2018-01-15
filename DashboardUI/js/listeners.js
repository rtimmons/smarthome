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
    e.app.onAction(action, args);
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
    e.app.onAction(action, args);
  }
}
