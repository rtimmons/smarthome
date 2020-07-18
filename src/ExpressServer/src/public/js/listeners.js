class ActiveCells {
    onMessage(e) {
        // TODO: move to onMessage for each cell
        e.Globals.App.eachCell(cell => {
            cell.setActive(cell.isActiveForRoom(e.Event.ToRoom));
        });
    }
}

class FetchStateOnRoomChange {
    onMessage(e) {
        // TODO: move to App
        e.Globals.App.fetchState();
    }
}

class RoomSaver {
    onMessage(e) {
        if (e.Topic == 'App.Initialized') {
            var room = window.cookies.get('Room') || 'Kitchen';
            e.Globals.App.changeRoom(room);
        }

        if (e.Topic != 'Room.Changed') {
            return;
        }

        window.cookies.set('Room', e.Event.ToRoom);
    }
}

class BackgroundChanger {
    onMessage(e) {
        var track = e.Event.State.currentTrack;

        var artUrl = track.absoluteAlbumArtUri || track.albumArtUri;
        e.Globals.App.setBackgroundImage(artUrl);

        var title = track.title;
        e.Globals.App.setBanner(title);
    }
}

class ZoneUpdater {
    // TODO: move to MusicController
    simplify(zones) {
        return zones.map(zone => {
            return {
                members: zone.members.map(m => m.roomName),
            };
        });
    }

    onMessage(e) {
        var zones = this.simplify(e.Event.Zones);
        e.Globals.App.updateZones(zones);
    }
}

class GenericOnPress {
    // TODO: move to Cell
    onMessage(e) {
        var onPress = e.Event.Cell.config.onPress;
        if (!onPress) {
            return;
        }

        var action = onPress.action;
        var args = onPress.args;
        e.Globals.App.onAction(action, args, e);
    }
}

class GenericOnDoublePress {
    // TODO: move to Cell
    onMessage(e) {
        var onPress = e.Event.Cell.config.onDoublePress;
        if (!onPress) {
            return;
        }

        var action = onPress.action;
        var args = onPress.args;
        e.Globals.App.onAction(action, args, e);
    }
}
