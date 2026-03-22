# Mind Maze Audio Assets

Drop your audio files into this structure:

assets/
  music/
    home.mp3
    gameplay.mp3
    win.mp3
    gameover.mp3
  sounds/
    click.wav
    hit.wav
    success.wav
    get_ready.wav
    oh_no.wav
    energetic_win.wav

Notes:
- Music files are state-driven and fade between screens.
- If a file is missing, the game automatically falls back to synthesized placeholder audio.
- Recommended levels:
  - Music: around 0.3-0.5 perceived loudness
  - SFX: around 0.7-1.0 perceived loudness
