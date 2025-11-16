class BlindControllerI2C {
    constructor(args) {
        this.requester = args.requester;
        this.root = args.root;
        this.app = args.app;
        this.pubsub = args.pubsub;
    }

    move([blind,direction]) { // [blind,direction]
        this.app.request({
            type: 'POST',
            url: `/blinds-i2c/${app.currentRoom()}_${blind.toLowerCase()}`,
            data: {
                state: direction.toLowerCase(),
            },
        });
    }
}
