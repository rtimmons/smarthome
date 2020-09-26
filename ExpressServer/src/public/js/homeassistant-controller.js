class HomeAssistantController {
    constructor(args) {
        this.requester = args.requester;
        this.root = args.root;
        this.app = args.app;
        this.pubsub = args.pubsub;
    }

    scene(paths) { // ['$room', 'High']
        const currRoom = this.app.currentRoom();
        const replaceName = n => n.replace(/\$room/g, currRoom);
        paths = paths.map(a => replaceName(a));
        // => ['Living', 'High']

        const path = '/scenes/scene_' + paths.join('_').replace(/\s+/g, '_').toLowerCase();
        console.log('Requesting scene at url ', path);
        this.app.request(path);
    }
}
