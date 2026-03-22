# Mind Maze

Cyberpunk memory maze game built with Pygame.

## Controls
- `WASD` / Arrow keys: move
- `H`: hint scan
- `F` or `SPACE`: focus mode
- `ESC`: back to menu

## Audio Controls
- `M`: mute/unmute all audio
- `-` / `+`: decrease/increase music volume
- `,` / `.`: decrease/increase SFX volume

## Audio Assets
Place audio files in:

```text
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
```

If any file is missing, the game automatically uses synthesized fallback audio.
