declare namespace SmartThings {

    export interface Capability {
        id: string;
        version: number;
    }

    export interface Component {
        id: string;
        label: string;
        capabilities: Capability[];
    }

    export interface DeviceTypeHandler {
        deviceTypeId: string;
        deviceTypeName: string;
        deviceNetworkType: string;
        completedSetup: boolean;
        networkSecurityLevel: string;
        hubId: string;
    }

    export interface Device {
        deviceId: string;
        name: string;
        label: string;
        locationId: string;
        roomId: string;
        deviceTypeId: string;
        deviceTypeName: string;
        deviceNetworkType: string;
        components: Component[];
        dth: DeviceTypeHandler;
        type: string;
        deviceManufacturerCode: string;
    }

    export interface Links {
    }

    export interface RootObject {
        items: Device[];
        _links: Links;
    }

}

