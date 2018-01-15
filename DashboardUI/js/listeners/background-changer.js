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
