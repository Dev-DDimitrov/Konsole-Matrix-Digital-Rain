# Controls

The controls apply to the public renderer commands described in
[GUIDE.md](GUIDE.md). `exit_guard` is an input guard, not authentication or a
secure lock; KDE/kscreenlocker remains the security boundary.

Run `matrix-guide --controls` for the current generated list.

| Key | Action |
| --- | --- |
| `1`–`7` | Select green, red, blue, white, yellow/amber, cyan, or magenta |
| `0` | Reset only hue position to canonical green |
| `c` | Toggle gradual color cycling |
| `C` | Reverse cycle direction from the exact current hue |
| `h` / `H` | Toggle hue-only hold/play |
| `v` / `V` | Slower/faster cycle speed |
| `p` / `P` | Freeze/resume the complete visual frame and cycle clock |
| `w` | Cycle white heads: 75% → 50% → 25% → 0% |
| `b` | Cycle profile, black, charcoal, white, translucent backgrounds |
| `Alt+Left` / `Alt+Right` | Nudge hue and automatically hold it |
| `Ctrl+L` | Lock/unlock live visual settings |
| `q`, `Escape`, `Space`, `Ctrl+C` | Exit unless `exit_guard` is enabled |

Settings lock blocks preference-changing controls but still permits pause/play,
help, status control, configured exit handling, and lifecycle cleanup. It is
not KDE locking, authentication, or `exit_guard`.

The safe default `exit_guard` state is disabled with `Ctrl+Y` as its binding.
