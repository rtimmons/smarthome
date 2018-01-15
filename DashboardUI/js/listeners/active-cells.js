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
