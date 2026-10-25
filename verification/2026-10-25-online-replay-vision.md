# Preserve eyesight in online journey screenshots

Vision sessions sent filtered screenshots for low vision, colour blindness and
aging eyes, while step replay rebuilt a sharp, unfiltered image. Researchers could
therefore see different visual evidence from the model whose choice they inspected.
Replay now applies the same eyesight transform and large-text setting, then marks
the chosen control. It retains the existing native-canvas replay resolution.

Twenty image comparisons capture the actual image delivered to a vision policy
at native width and compare replay pixels outside the selected-control highlight.
They cover four eyesight modes, mobile/desktop, normal/large text, shuffled option
numbers and no-choice steps; selected-control border location is also checked.
Before repair: 15 failed, 5 passed in 8.95 seconds. After repair: 57 focused engine
and API tests passed in 29.27 seconds. Full-source Pyright reported zero errors and
warnings and backend boot passed. The capturing policy used no real model service.
