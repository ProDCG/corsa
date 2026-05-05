import sys
import time

try:
    import pygame
except ImportError:
    print("Error: The 'pygame' library is required to read controller inputs.")
    print("Please install it by running: pip install pygame")
    sys.exit(1)

def main():
    pygame.init()
    pygame.joystick.init()

    # Create a small window. Pygame REQUIRES a focused window to capture keyboard events!
    screen = pygame.display.set_mode((400, 200))
    pygame.display.set_caption("CLICK ME FOR INPUTS")
    
    font = pygame.font.SysFont(None, 24)
    text = font.render("Keep this window focused!", True, (255, 255, 255))
    screen.blit(text, (20, 80))
    pygame.display.flip()

    joystick_count = pygame.joystick.get_count()
    if joystick_count == 0:
        print("No controllers or steering wheels found. Please ensure it is plugged in.")
        sys.exit(0)

    print(f"Found {joystick_count} controller(s):")
    joysticks = []
    for i in range(joystick_count):
        joy = pygame.joystick.Joystick(i)
        joy.init()
        joysticks.append(joy)
        print(f"  [{i}] {joy.get_name()} (Buttons: {joy.get_numbuttons()}, Axes: {joy.get_numaxes()}, Hats: {joy.get_numhats()})")

    print("\nListening for inputs... Press Ctrl+C to exit.")
    print("-" * 50)

    try:
        while True:
            # Pump events so pygame reads from the OS
            pygame.event.pump()
            
            for event in pygame.event.get():
                if event.type == pygame.JOYBUTTONDOWN:
                    print(f"[BUTTON PRESSED] Controller {event.joy} | Button ID: {event.button}")
                elif event.type == pygame.JOYBUTTONUP:
                    print(f"[BUTTON RELEASED] Controller {event.joy} | Button ID: {event.button}")
                elif event.type == pygame.JOYHATMOTION:
                    print(f"[D-PAD/HAT] Controller {event.joy} | Hat {event.hat} | Value: {event.value}")
                # We typically ignore JOYAXISMOTION (steering/pedals) in this output 
                # to prevent console spam from micro-movements, but you can uncomment this if needed:
                # elif event.type == pygame.JOYAXISMOTION:
                #     if abs(event.value) > 0.1:  # Only print significant movements
                #         print(f"[AXIS] Controller {event.joy} | Axis {event.axis} | Value: {event.value:.2f}")
                elif event.type == pygame.KEYDOWN:
                    print(f"[KEYBOARD PRESSED] Key: {pygame.key.name(event.key)}")

            time.sleep(0.01)

    except KeyboardInterrupt:
        print("\nExiting...")
    finally:
        pygame.quit()

if __name__ == "__main__":
    main()
