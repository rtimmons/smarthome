class ActiveCells {
    onMessage(e) {
        // TODO: move to onMessage for each cell
        e.Globals.App.eachCell(cell => {
            if (!cell.config || !cell.config.activeWhenRoom) {
                return;
            }
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

function displayedIntent(status) {
    if (!status) {
        return null;
    }

    return status.activeIntent || status.recentIntent || null;
}

function zoneMembersForRoom(zones, roomName) {
    if (!Array.isArray(zones) || !roomName) {
        return null;
    }

    var zone = zones.find(candidate =>
        Array.isArray(candidate.members) &&
        candidate.members.indexOf(roomName) >= 0
    );
    return zone ? zone.members : null;
}

function reconcileGroupAllIntent(intent, zones) {
    if (
        !intent ||
        !intent.targetRoom ||
        !Array.isArray(intent.roomNames)
    ) {
        return intent;
    }

    var members = zoneMembersForRoom(zones, intent.targetRoom);
    if (!members) {
        return intent;
    }

    var joinedRooms = intent.roomNames.filter(
        roomName => members.indexOf(roomName) >= 0
    );
    var missingRooms = intent.roomNames.filter(
        roomName => joinedRooms.indexOf(roomName) < 0
    );
    var observedComplete = missingRooms.length === 0;
    var message = intent.message;

    if (observedComplete) {
        message =
            'Joined all to ' +
            intent.targetRoom +
            ' (' +
            joinedRooms.length +
            '/' +
            intent.roomNames.length +
            ')';
    } else if (intent.status === 'running') {
        message =
            'Joining all to ' +
            intent.targetRoom +
            ' (' +
            joinedRooms.length +
            '/' +
            intent.roomNames.length +
            ')';
    }

    return Object.assign({}, intent, {
        joinedRooms: joinedRooms,
        missingRooms: missingRooms,
        observedComplete: observedComplete,
        message: message,
    });
}

function reconcileIntentStatus(status, zones) {
    if (!status || !Array.isArray(zones)) {
        return status || {};
    }

    return Object.assign({}, status, {
        activeIntent: reconcileGroupAllIntent(status.activeIntent, zones),
        recentIntent: reconcileGroupAllIntent(status.recentIntent, zones),
    });
}

function zoneMutationSatisfied(mutation, zones) {
    if (!mutation || !Array.isArray(zones)) {
        return false;
    }

    var anchorMembers = zoneMembersForRoom(zones, mutation.anchorRoom);
    var roomMembers = zoneMembersForRoom(zones, mutation.room);
    if (!anchorMembers || !roomMembers) {
        return false;
    }

    if (mutation.desiredJoined) {
        return anchorMembers.indexOf(mutation.room) >= 0;
    }

    if (mutation.room === mutation.anchorRoom) {
        return roomMembers.length === 1;
    }

    return anchorMembers.indexOf(mutation.room) < 0;
}

function intentBannerText(status) {
    var intent = displayedIntent(status);
    if (!intent || !intent.message) {
        return '';
    }

    return intent.message;
}

function intentHasError(status) {
    var intent = displayedIntent(status);
    if (!intent) {
        return false;
    }

    return (
        !intent.observedComplete &&
        (intent.status === 'failed' || intent.status === 'timed_out')
    );
}

class BackgroundChanger {
    onMessage(e) {
        var state = (e.Event && e.Event.State) || {};
        var meta = (e.Event && e.Event.Meta) || {};
        var track = state.currentTrack;
        e.Globals.App.setSonosStateStale(meta.stale);
        if (!track) {
            e.Globals.App.setBackgroundImage('');
            e.Globals.App.setTrackBanner('');
            return;
        }

        var artUrl = track.absoluteAlbumArtUri || track.albumArtUri;
        e.Globals.App.setBackgroundImage(artUrl);

        var bannerText = formatBannerText(track);
        if (meta.stale && meta.ageMs > 0) {
            bannerText = [bannerText, '(stale ' + Math.round(meta.ageMs / 1000) + 's)']
                .filter(Boolean)
                .join(' ');
        }
        e.Globals.App.setTrackBanner(bannerText);
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
        var meta = (e.Event && e.Event.Meta) || {};
        if (meta.unknown || meta.stale) {
            e.Globals.App.setZonesUnknown(true);
            return;
        }

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

class IntentUpdater {
    onMessage(e) {
        var status = e.Event.Status || {};
        e.Globals.App.updateIntentStatus(status);
    }
}

if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        ActiveCells: ActiveCells,
        displayedIntent: displayedIntent,
        formatBannerText: formatBannerText,
        intentBannerText: intentBannerText,
        intentHasError: intentHasError,
        parseSiriusMetadata: parseSiriusMetadata,
        reconcileIntentStatus: reconcileIntentStatus,
        zoneMutationSatisfied: zoneMutationSatisfied,
    };
}
