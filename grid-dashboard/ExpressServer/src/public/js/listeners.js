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

function normalizeBannerValue(value) {
    if (typeof value !== 'string') {
        return '';
    }
    return value.trim();
}

function parseSiriusMetadataSegment(segment) {
    var normalized = normalizeBannerValue(segment);
    if (!normalized) {
        return null;
    }

    var equalsMatch = normalized.match(/^([A-Z]+)=(.*)$/);
    if (equalsMatch) {
        return {
            key: equalsMatch[1],
            value: normalizeBannerValue(equalsMatch[2]),
        };
    }

    var spacedMatch = normalized.match(/^([A-Z]+)\s+(.+)$/);
    if (spacedMatch) {
        return {
            key: spacedMatch[1],
            value: normalizeBannerValue(spacedMatch[2]),
        };
    }

    return null;
}

function parseSiriusMetadata(value) {
    var normalized = normalizeBannerValue(value);
    if (!normalized || normalized.indexOf('|') < 0) {
        return null;
    }

    var metadata = {};
    normalized.split('|').forEach(segment => {
        var parsed = parseSiriusMetadataSegment(segment);
        if (!parsed || !parsed.key || !parsed.value) {
            return;
        }
        metadata[parsed.key] = parsed.value;
    });

    if (!metadata.TITLE && !metadata.ARTIST) {
        return null;
    }

    return metadata;
}

function parseTrackMetadata(track) {
    if (!track) {
        return {};
    }

    var titleMetadata = parseSiriusMetadata(track.title);
    var artistMetadata = parseSiriusMetadata(track.artist);
    var albumMetadata = parseSiriusMetadata(track.album);
    return Object.assign({}, albumMetadata, artistMetadata, titleMetadata);
}

function formatBannerText(track) {
    if (!track) {
        return '';
    }

    var siriusMetadata = parseTrackMetadata(track);
    var title = normalizeBannerValue(siriusMetadata.TITLE || track.title);
    var artist = normalizeBannerValue(
        siriusMetadata.ARTIST || track.artist || track.stationName
    );

    if (siriusMetadata.TITLE) {
        return [title, artist].filter(Boolean).join(' - ');
    }

    return [title, artist].filter(Boolean).join(' — ');
}

class BackgroundChanger {
    onMessage(e) {
        var state = (e.Event && e.Event.State) || {};
        var track = state.currentTrack;
        if (!track) {
            e.Globals.App.setBackgroundImage('');
            e.Globals.App.setBanner('');
            return;
        }

        var artUrl = track.absoluteAlbumArtUri || track.albumArtUri;
        e.Globals.App.setBackgroundImage(artUrl);

        var bannerText = formatBannerText(track);
        e.Globals.App.setBanner(bannerText);
    }
}

class ZoneUpdater {
    // TODO: move to MusicController
    simplify(zones) {
        if (!Array.isArray(zones)) {
            return [];
        }
        return zones.map(zone => {
            return {
                members: (zone.members || []).map(m => m.roomName),
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

if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        formatBannerText: formatBannerText,
        parseSiriusMetadata: parseSiriusMetadata,
    };
}
