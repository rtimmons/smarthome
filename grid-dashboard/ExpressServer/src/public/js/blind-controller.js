class BlindController {
    constructor(args) {
        this.requester = args.requester;
        this.root = args.root;
        this.app = args.app;
        this.pubsub = args.pubsub;
    }

    move([direction]) {
        this.app.request({
            type: 'POST',
            url: `/blinds/${app.currentRoom()}`,
            data: {
                state: direction.toLowerCase(),
            },
        });
    }
}
