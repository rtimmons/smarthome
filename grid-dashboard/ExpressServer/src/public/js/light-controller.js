class LightController {
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
        // => ['Living Room', 'High']

        const scenePath = 'scenes/scene_' + paths.join('_').replace(/\s+/g, '_').toLowerCase();

        // Build URL using current page's base path for ingress compatibility
        let url;
        if (!this.root) {
            // Get base path from current location, removing ALL trailing slashes
            const basePath = window.location.pathname.replace(/\/+$/, ''); // Remove all trailing slashes
            url = basePath + '/' + scenePath;
        } else {
            url = this.root + '/' + scenePath;
        }

        console.log('Requesting scene at url ', url);
        this.app.request(url);
    }
}
