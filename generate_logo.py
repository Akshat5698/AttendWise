from PIL import Image, ImageDraw, ImageFont

# Create a 120x120 PNG
img = Image.new("RGBA", (120, 120), "#0e1117")
draw = ImageDraw.Draw(img)

# Draw a simple circle
draw.ellipse((10, 10, 110, 110), fill="#1f2937")

# Add text "CB"
draw.text((40, 45), "CB", fill="white")

# Save logo
img.save("assets/logo.png")

print("logo.png created successfully")
