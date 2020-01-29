class BlindController {
    constructor(args) {
        this.requester = args.requester;
        this.root = args.root;
        this.app = args.app;
        this.pubsub = args.pubsub;
    }

    move(args) { // ['$room', 'Up/Down/Mid']
        const currRoom = this.app.currentRoom();
        //const replaceName = n => n.replace(/\$room/g, currRoom);
        //paths = paths.map(a => replaceName(a));
        // => ['Living', 'High']

        const path = 'http://raspberrypi.local/BlindControl/cgi-bin/blind-control.py?room=' + currRoom + '&direction=' + args[0];
        console.log('Requesting to move blinds at url ', path);
        this.app.request(path);
    }
}
