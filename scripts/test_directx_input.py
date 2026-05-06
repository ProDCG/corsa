import time
import sys

try:
    import pydirectinput
except ImportError:
    print("Please install pydirectinput first: pip install pydirectinput")
    sys.exit(1)

print("Get ready! Switching to Assetto Corsa...")
print("You have 5 seconds to click into the Assetto Corsa window (the pit menu)...")

for i in range(5, 0, -1):
    print(i)
    time.sleep(1)

print("Sending DirectX-level Ctrl+Space...")

# pydirectinput sends inputs at the DirectX level, which games cannot ignore
pydirectinput.keyDown('ctrl')
pydirectinput.press('space')
pydirectinput.keyUp('ctrl')

print("Done! Did it drop you into the car?")
