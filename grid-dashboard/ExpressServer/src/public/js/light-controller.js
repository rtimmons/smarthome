class LightController {
    constructor(args) {
        this.requester = args.requester;
        this.root = args.root;
        this.app = args.app;
        this.pubsub = args.pubsub;
        this.sceneRooms = args.sceneRooms || {};
    }

    scene(paths) { // ['$room', 'High']
        const currRoom = this.app.currentRoom();
        const replaceName = n => {
            if (n !== '$room') {
                return n;
            }
            const sceneRoom = this.sceneRooms[currRoom];
            if (!sceneRoom) {
                throw new Error('No lighting scenes configured for room: ' + currRoom);
            }
            return sceneRoom;
        };
        paths = paths.map(a => replaceName(a));
        // => ['living_room', 'High']

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
        return this.app.request({
            url: url,
            method: 'POST',
        });
    }
}

if (typeof module !== 'undefined' && module.exports) {
    module.exports = LightController;
}
