from PIL import Image, ImageDraw
import math

def create_hexagon_icon(size=256, color="#A78BFA", bg="#1B1E2B"):
    # Create image with transparent background
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Hexagon points calculation
    cx, cy = size // 2, size // 2
    r = (size // 2) - 20
    points = []
    for i in range(6):
        angle_deg = 60 * i - 30
        angle_rad = math.pi / 180 * angle_deg
        x = cx + r * math.cos(angle_rad)
        y = cy + r * math.sin(angle_rad)
        points.append((x, y))

    # Draw background hexagon
    draw.polygon(points, fill=bg)

    # Draw border hexagon
    draw.polygon(points, outline=color, width=12)

    # Inner pulse dot (Network Nexus style)
    ir = int(r // 2.5)
    draw.ellipse((cx-ir, cy-ir, cx+ir, cy+ir), fill=color)

    # Save as ICO (multiple sizes)
    img.save("icon.ico", format="ICO", sizes=[(16,16), (32,32), (48,48), (64,64), (128,128), (256,256)])
    print("icon.ico created.")

if __name__ == "__main__":
    create_hexagon_icon()
