# Render with: vhs demo.tape  → demo.gif
#
# RECORDING PROTOCOL: run `cocoa demo` once BEFORE recording so the fixture
# clone and per-service analysis caches are warm — the recorded run then
# completes in seconds instead of minutes and the GIF stays tight. Do NOT
# record a cold run: analysis time varies with toolchain availability and
# a fixed Sleep will truncate it.
Output demo.gif
Set FontSize 15
Set Width 1200
Set Height 640
Set Theme "Catppuccin Mocha"

Type "cocoa demo"
Enter
Sleep 25s
Type "cocoa blast -p ~/.cocoa/demo/microservices-demo-v0.10.5 --target hipstershop.Money.units --kind proto-field"
Enter
Sleep 10s
