import { expect } from 'chai';
import * as fs from 'fs';
import * as path from 'path';

const lightController: any = require('./light-controller');
const dashboardConfig: any = require('./config');

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
                sceneRooms: dashboardConfig.lightSceneRooms,
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

    it('maps every configured room preset to a generated fast scene', () => {
        const generatedScripts = fs.readFileSync(
            path.resolve(
                process.cwd(),
                '../../new-hass-configs/generated/scripts.yaml'
            ),
            'utf8'
        );

        Object.values(dashboardConfig.lightSceneRooms).forEach((room: any) => {
            ['high', 'medium', 'off'].forEach(preset => {
                expect(generatedScripts).to.include(
                    'fast_scene_' + room + '_' + preset + ':'
                );
            });
        });
    });

    it('maps the Move room controls to the outdoor scenes', () => {
        const requests: any[] = [];
        const previousWindow = (global as any).window;
        (global as any).window = { location: { pathname: '' } };

        try {
            const controller = new lightController({
                app: {
                    currentRoom: () => 'Move',
                    request: (request: any) => requests.push(request),
                },
                root: '',
                sceneRooms: dashboardConfig.lightSceneRooms,
            });

            controller.scene(['$room', 'Medium']);

            expect(requests).to.deep.equal([
                {
                    url: '/scenes/scene_outdoor_medium',
                    method: 'POST',
                },
            ]);
        } finally {
            (global as any).window = previousWindow;
        }
    });
});
