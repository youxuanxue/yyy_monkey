import os
from PIL import Image

def generate_icons():
    source_path = "/Users/xuejiao/Codes/yyy_monkey/auto_helper/extension/assets/icons/bmo.png"
    target_dir = "/Users/xuejiao/Codes/yyy_monkey/auto_helper/extension/assets/icons/"
    
    if not os.path.exists(source_path):
        print(f"Error: Source image not found at {source_path}")
        return

    try:
        with Image.open(source_path) as img:
            sizes = [16, 48, 128]
            for size in sizes:
                resized_img = img.resize((size, size), Image.Resampling.LANCZOS)
                output_path = os.path.join(target_dir, f"icon{size}.png")
                resized_img.save(output_path)
                print(f"Generated {output_path}")
    except Exception as e:
        print(f"Error processing image: {e}")

if __name__ == "__main__":
    generate_icons()
