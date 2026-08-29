# Sonos source compatibility contract

Home Assistant and `node-sonos-http-api` expose the same broad transport
concepts, but they do not expose a common source vocabulary. The compatibility
layer therefore normalizes the legacy state shape while preserving the
source-specific input and output rules below.

## Source matrix

| Source family | Home Assistant input | Node API input (legacy) | Expected Home Assistant state | Compatibility rule |
| --- | --- | --- | --- | --- |
| SiriusXM/radio favorite | `media_player.select_source` with the exact favorite title, or `media_player.play_media` with a favorite item ID | `/sonos/<room>/favorite/<name>` or the node SiriusXM action | `media_content_type: music`, an `x-sonosapi-hls:` `media_content_id`, current song in `media_title`/`media_artist`, and station identity in `media_channel`; `source` may be `null` | Project `media_channel` to `stationName`; do not require `source` to equal the station. The station identity is the channel/URI, not the changing song title. |
| Apple Music | `media_player.play_media` with an Apple Music share link or a repository-owned favorite item ID | Node-only `/applemusic/{now,next,queue}/song|album|playlist:<id>` actions | Music or playlist metadata and a service URI (`x-sonos-http:` or `x-rincon-cpcontainer:`); `source` and `source_list` need not contain `Apple Music` | Do not route Apple Music through `select_source` unless it is an exact, observed favorite title. Preserve the media ID/type and test replace, add, and next queue modes independently. |
| TV/SPDIF | `media_player.select_source` with exact source `TV` on a TV-capable coordinator | Legacy presets used UUID-bearing `x-sonos-htastream:RINCON…:spdif` URIs | `source: TV`, title commonly `TV`, no meaningful position/duration, and a dynamic `x-sonos-htastream:` ID | Repository presets contain only `TV`; never persist a RINCON/UUID or compare the returned stream URI literally. Validate that the coordinator advertises `TV` before writing. |
| Local line-in | `media_player.select_source` with exact source `Line-in` on a line-in-capable player | `/sonos/<room>/linein[/<source-room>]`, which builds `x-rincon-stream:<UUID>` | `source: Line-in`, title commonly `Line-in`, and cleared/near-zero position/duration; stream URI identity is dynamic | `Line-in` is a physical input, not a favorite. The retained TV-preset API does not implicitly expose remote line-in routing; any future route must use an allowlisted source room and tolerate dynamic UUIDs. |
| Other Sonos favorites/playlists | Exact title via `select_source`, or stable favorite item ID via `play_media` | `/favorite/<name>` with node-specific direct-play/queue behavior | Metadata and URI depend on the favorite; source title may be absent or provider-specific | Match titles exactly against the live `source_list`; reject missing or case-changed names before a service call. Prefer a favorite item ID for new stable automations. |

## Field and ownership rules

The legacy state projection keeps one shape for all source families:

- `playbackState`, metadata, artwork, URI, and elapsed time are owned by the
  observed group coordinator.
- `volume` and `mute` are owned by the requested member.
- `currentTrack.type` keeps the node parser's source-family labels (`radio`,
  `track`, `line_in`) by classifying the Home Assistant URI/source. The HA
  `media_content_type` remains an input detail and is not copied into this
  legacy field (`music` would incorrectly classify SiriusXM and TV).
- `currentTrack.stationName` is `media_channel` when present. For Apple Music,
  TV, and line-in it is normally empty or the physical-input label.
- `currentTrack.uri` and `trackUri` preserve `media_content_id`; tests must
  assert the URI family and required identity, not a literal UUID.
- `source` is an input/action selector, not a universal provider field. It is
  intentionally not added to the legacy state response.
- Position and duration are meaningful for on-demand media and may advance
  while playing. Live radio, TV, and line-in may report zero or non-seeking
  values; parity tests exclude elapsed time where the two backends use
  independent clocks.

## Action rules

1. Favorites use exact, observed `source_list` title matching. Invalid, missing,
   or case-changed titles fail before any Home Assistant call.
2. TV and line-in use exact physical source names and are model-dependent. A
   source-list absence is a readiness/diagnostic failure according to backend
   mode, never a reason to send a raw stream URI.
3. Apple Music is a `play_media` contract (share link or favorite item ID), not
   a physical source. The old node Apple Music endpoint is not silently mapped
   to `select_source`.
4. A source action targets the requested allowlisted member. Group topology is
   observed separately; metadata/artwork still follow the coordinator.
5. Every source transition is followed by an authoritative state observation.
   Dynamic stream IDs, song titles, and elapsed positions are not used as
   topology success signals.

## Regression and live evidence

The automated source matrix is covered by:

- `home-assistant-sonos-state.spec.ts`: SiriusXM/radio, Apple Music, TV, and
  line-in projection fixtures, including coordinator metadata versus member
  volume/mute ownership.
- `home-assistant-sonos-actions.spec.ts`: exact favorite, `TV`, and `Line-in`
  source selection, invalid-title rejection, and zero-write validation.
- `home-assistant-sonos-presets.spec.ts`: UUID-free TV preset plans and exact
  source steps.
- Runtime health tests: every configured favorite and every TV preset source is
  checked against the live `source_list` before HA mode is ready.

Live rollout must add one low-risk observation for an Apple Music item, one TV
preset, and one line-in transition when those capabilities are available. Each
test captures and restores the household's current group, volumes, mute values,
and station; a failed or unavailable capability is recorded as a blocked live
check rather than treated as source parity.
