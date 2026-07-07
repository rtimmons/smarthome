import { expect } from 'chai';

const lightController: any = require('./light-controller');

describe('LightController', () => {
    it('posts the current room high scene through the ingress path', () => {
        const requests: any[] = [];
        const previousWindow = (global as any).window;
        (global as any).window = {
            location: {
                pathname: '/api/hassio_ingress/token/',
            },
        };

        try {
            const controller = new lightController({
                app: {
                    currentRoom: () => 'Living Room',
                    request: (request: any) => requests.push(request),
                },
                root: '',
            });

            controller.scene(['$room', 'High']);

            expect(requests).to.deep.equal([
                {
                    url:
                        '/api/hassio_ingress/token/scenes/scene_living_room_high',
                    method: 'POST',
                },
            ]);
        } finally {
            (global as any).window = previousWindow;
        }
    });
});
