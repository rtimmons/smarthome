declare module namespace {

    export interface Equalizer {
        bass: number;
        treble: number;
        loudness: boolean;
        speechEnhancement: boolean;
        nightMode: boolean;
    }

    export interface CurrentTrack {
        artist: string;
        title: string;
        album: string;
        albumArtUri: string;
        duration: number;
        uri: string;
        trackUri: string;
        type: string;
        stationName: string;
    }

    export interface NextTrack {
        artist: string;
        title: string;
        album: string;
        albumArtUri: string;
        duration: number;
        uri: string;
    }

    export interface PlayMode {
        repeat: string;
        shuffle: boolean;
        crossfade: boolean;
    }

    export interface Sub {
        gain: number;
        crossover: number;
        polarity: number;
        enabled: boolean;
    }

    export interface State {
        volume: number;
        mute: boolean;
        equalizer: Equalizer;
        currentTrack: CurrentTrack;
        nextTrack: NextTrack;
        trackNo: number;
        elapsedTime: number;
        elapsedTimeFormatted: string;
        playbackState: string;
        playMode: PlayMode;
        sub: Sub;
    }

    export interface GroupState {
        volume: number;
        mute: boolean;
    }

    export interface Coordinator {
        uuid: string;
        state: State;
        roomName: string;
        coordinator: string;
        groupState: GroupState;
    }

    export interface Equalizer2 {
        bass: number;
        treble: number;
        loudness: boolean;
        speechEnhancement?: boolean;
        nightMode?: boolean;
    }

    export interface CurrentTrack2 {
        artist: string;
        title: string;
        album: string;
        albumArtUri: string;
        duration: number;
        uri: string;
        trackUri: string;
        type: string;
        stationName: string;
    }

    export interface NextTrack2 {
        artist: string;
        title: string;
        album: string;
        albumArtUri: string;
        duration: number;
        uri: string;
    }

    export interface PlayMode2 {
        repeat: string;
        shuffle: boolean;
        crossfade: boolean;
    }

    export interface Sub2 {
        gain: number;
        crossover: number;
        polarity: number;
        enabled: boolean;
    }

    export interface MemberState {
        volume: number;
        mute: boolean;
        equalizer: Equalizer2;
        currentTrack: CurrentTrack2;
        nextTrack: NextTrack2;
        trackNo: number;
        elapsedTime: number;
        elapsedTimeFormatted: string;
        playbackState: string;
        playMode: PlayMode2;
        sub: Sub2;
    }

    export interface GroupState2 {
        volume: number;
        mute: boolean;
    }

    export interface Member {
        uuid: string;
        state: MemberState;
        roomName: string;
        coordinator: string;
        groupState: GroupState2;
    }

    export interface RootObject {
        uuid: string;
        coordinator: Coordinator;
        members: Member[];
    }

}

