# The service lifecycle, recorded against the same scenario the simulated
# dashboard replays. Run it through scripts/record_demo.sh, which seeds the
# sandbox this expects; running `vhs` on it directly would touch real config.

Output site/public/media/services.gif

Set Shell bash
Set FontSize 18
Set Width 1180
Set Height 660
Set Padding 24
Set Margin 16
Set BorderRadius 10
Set Theme "Catppuccin Mocha"
Set TypingSpeed 45ms
Set PlaybackSpeed 1

# The scenario's machine already has these two up, the same as the dashboard
# demo opens with, so both show the same starting point.
Hide
Type "LocalSM up web && LocalSM up docs && clear" Enter
Sleep 2s
Show

Type "LocalSM status" Sleep 400ms Enter
Sleep 3s

Type "LocalSM up api" Sleep 400ms Enter
Sleep 2.5s

Type "LocalSM logs api" Sleep 400ms Enter
Sleep 2.5s

Type "LocalSM --json status api" Sleep 400ms Enter
Sleep 3s

Type "LocalSM down api" Sleep 400ms Enter
Sleep 2.5s
