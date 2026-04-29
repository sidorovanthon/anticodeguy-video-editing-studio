# Seam plan: 2026-04-28-integration-fixture (master_duration_ms=37000)

## Scene 1
- start_ms: 0
- end_ms: 3000
- beat_id: B1
- narrative_position: opening
- energy_hint: medium
- mode: head
- transition_out: crossfade
- key_phrase: "desktop software licensing"
- graphic:
  - source: none

  script: |
    Hello today the topic is desktop software licensing.

## Scene 2
- start_ms: 3000
- end_ms: 7500
- beat_id: B2
- narrative_position: setup
- energy_hint: medium
- mode: split
- transition_out: push-slide
- key_phrase: "three approaches"
- graphic:
  - source: generative
  - brief: |
      Right-side panel: three labelled vertical columns sliding in
      left-to-right with 120 ms staggers, each column tagged with
      one of the three licensing approaches.

  script: |
    There are three approaches that ship in the wild.

## Scene 3
- start_ms: 7500
- end_ms: 12000
- beat_id: B3
- narrative_position: main
- energy_hint: medium
- mode: broll
- transition_out: cut
- key_phrase: "online check"
- graphic:
  - source: generative
  - brief: |
      Animated network handshake diagram: a desktop client sends a
      license-check request over a stylised globe to a remote server,
      the response pulses back as a green checkmark.

  script: |
    First approach: online check.

## Scene 4
- start_ms: 12000
- end_ms: 16500
- beat_id: B4
- narrative_position: main
- energy_hint: medium
- mode: broll
- transition_out: cut
- key_phrase: "hardware key"
- graphic:
  - source: generative
  - brief: |
      Close-up rendering of a USB hardware dongle being inserted into
      a laptop port; an LED pulses amber then locks to solid green
      while a key-shaped icon overlays the dongle silhouette.

  script: |
    Second approach: hardware key.

## Scene 5
- start_ms: 16500
- end_ms: 21000
- beat_id: B5
- narrative_position: main
- energy_hint: medium
- mode: broll
- transition_out: crossfade
- key_phrase: "time-based expiry"
- graphic:
  - source: generative
  - brief: |
      Calendar grid sweeping forward day by day; a license badge
      starts opaque and fades to transparent as the cursor crosses
      the expiry date, with a hourglass icon draining alongside.

  script: |
    Third approach: time-based expiry.

## Scene 6
- start_ms: 21000
- end_ms: 23000
- beat_id: B6
- narrative_position: climax
- energy_hint: high
- mode: overlay
- transition_out: cut
- key_phrase: "breaks differently"
- graphic:
  - source: catalog/lower-third
  - data: {"text": "Each one breaks differently."}

  script: |
    Each one breaks differently.

## Scene 7
- start_ms: 23000
- end_ms: 27500
- beat_id: B7
- narrative_position: main
- energy_hint: high
- mode: broll
- transition_out: cut
- key_phrase: "like this"
- graphic:
  - source: generative
  - brief: |
      Split-screen failure montage panel one: a connection-lost spinner
      stuck mid-rotation while a license-server URL greys out, frame
      shaking subtly to convey timeout frustration.

  script: |
    Like this.

## Scene 8
- start_ms: 27500
- end_ms: 30000
- beat_id: B8
- narrative_position: wind_down
- energy_hint: medium
- mode: head
- transition_out: crossfade
- key_phrase: "and like this"
- graphic:
  - source: none

  script: |
    And like this.

## Scene 9
- start_ms: 30000
- end_ms: 34500
- beat_id: B9
- narrative_position: main
- energy_hint: medium
- mode: broll
- transition_out: crossfade
- key_phrase: "and finally this"
- graphic:
  - source: generative
  - brief: |
      Wall-clock close-up advancing past the trial expiry minute; the
      desktop application window behind it greys out and a modal
      lock icon snaps into the centre with a soft thud.

  script: |
    And finally this.

## Scene 10
- start_ms: 34500
- end_ms: 37000
- beat_id: B10
- narrative_position: outro
- energy_hint: medium
- mode: overlay
- transition_out: cut
- key_phrase: "please subscribe"
- graphic:
  - source: catalog/subscribe-cta

  script: |
    Thanks for watching, please subscribe.
