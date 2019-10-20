declare namespace Sonos {
  export interface Equalizer {
    bass: number;
    treble: number;
    loudness: boolean;
    speechEnhancement?: boolean;
    nightMode?: boolean;
  }

  export interface Track {
    artist: string;
    title: string;
    album: string;
    albumArtUri: string;
    duration: number;
    uri: string;
  }

  export interface CurrentTrack extends Track {
    trackUri: string;
    type: string;
    stationName: string;
  }

  export interface PlayMode {
    repeat: 'none' | 'one' | 'all';
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
    nextTrack: Track;
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

  export interface Member {
    uuid: string;
    state: State;
    roomName: string;
    coordinator: string;
    groupState: GroupState;
  }

  export interface Zone {
    uuid: string;
    coordinator: Member;
    members: Member[];
  }
}
