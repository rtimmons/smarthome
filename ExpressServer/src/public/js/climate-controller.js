class ClimateController {
    constructor(args) {
        this.requester = args.requester;
        this.root = args.root;
        this.app = args.app;
        this.pubsub = args.pubsub;
    }

    set_temperature(entity_id, temperature) {
        const path = `/set_temperature/${entity_id}/${temperature}`;
        console.log('Requesting temperature change at url ', path);
        this.app.request(path);
    }
}
