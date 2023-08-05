import * as VIAM from '@viamrobotics/sdk';

class BlindControllerI2C {
    constructor(args) {
        this.requester = args.requester;
        this.root = args.root;
        this.app = args.app;
        this.pubsub = args.pubsub;
    }

    async move([blind,direction]) { // [blind,direction]
        robot_control(blind, direction)
        // this.app.request({
        //     type: 'POST',
        //     url: `/blinds-i2c/${app.currentRoom()}_${blind.toLowerCase()}`,
        //     data: {
        //         state: direction.toLowerCase(),
        //     },
        // });
    }
}

const rooms = {
    // bedroom_roller: new Blind({
    //     up: {address: 0x11, bit: 0x2},
    //     down: {address: 0x11, bit: 0x1}
    // }),
    bedroom_blackout: {
        up: {address: 0x11, bit: 0x08},
        down: {address: 0x12, bit: 0x04},
        mid: {address: 0x11, bit: 0x04}
    },
    // living_roller: new Blind({
    //     up: {address: 0x13, bit: 0x02},
    //     down: {address: 0x13, bit: 0x01}
    // }),
    // office_roller: new Blind({
    //     up: {address: 0x12, bit: 0x02},
    //     down: {address: 0x12, bit: 0x01}
    // }),
    // office_blackout: new Blind({
    //     up: {address: 0x13, bit: 0x08},
    //     down: {address: 0x13, bit: 0x04},
    //     mid: {address: 0x12, bit: 0x08}
    // }),
};

async function robot_control(blind, direction) {
  const host = 'blinds.m027aso1s5.viam.cloud';

  const robot = await VIAM.createRobotClient({
    host,
    credential: {
      type: 'robot-location-secret',
      payload: '',
    },
    authEntity: host,
    signalingAddress: 'https://app.viam.com:443',
  });
  
  blind = rooms[blind][direction]

  console.log('Resources:');
  console.log(await robot.resourceNames());

  const genericClient = new VIAM.GenericClient(robot, 'blinds');
  const returnValue = await genericClient.doCommand({"pulse_one":{"address":blind.address, "bit":blind.bit, "pulse_seconds": "1"}});
  console.log('board getGPIO return value:', returnValue);
}

main().catch((error) => {
  console.error('encountered an error:', error)
});