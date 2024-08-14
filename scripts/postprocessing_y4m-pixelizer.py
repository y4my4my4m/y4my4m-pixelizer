import os
import gradio as gr
from modules import scripts_postprocessing, devices, scripts, ui_components
from modules.ui_components import FormRow
from PIL import Image
import time

def is_within_tolerance(pixel, reference_pixel, tolerance):
    return all(abs(pixel[i] - reference_pixel[i]) <= tolerance for i in range(3))  # Compare RGB channels only

def process_image(img, pixel_size, upscale_after, tolerance):
    # Scale down the image by the pixel size using nearest neighbor
    width, height = img.size
    scaled_width = width // pixel_size
    scaled_height = height // pixel_size

    img = img.resize((scaled_width, scaled_height), Image.Resampling.NEAREST)

    if tolerance != 0:
        # Make the first pixel (top-left) transparent across the entire image
        img = img.convert("RGBA")
        top_left_pixel = img.getpixel((0, 0))

        # Loop through the pixels and set the matching ones to transparent
        for x in range(scaled_width):
            for y in range(scaled_height):
                current_pixel = img.getpixel((x, y))
                if is_within_tolerance(current_pixel, top_left_pixel, tolerance):
                    img.putpixel((x, y), (0, 0, 0, 0))

    # Optionally scale the image back up
    if upscale_after:
        img = img.resize((width, height), Image.Resampling.NEAREST)

    return img


def separate_sprites(img):
    width, height = img.size
    sprites = []
    visited = [[False for _ in range(width)] for _ in range(height)]

    def flood_fill(x, y, bounds):
        queue = [(x, y)]
        visited[y][x] = True

        while queue:
            cx, cy = queue.pop(0)
            bounds[0] = min(bounds[0], cx)  # left
            bounds[1] = min(bounds[1], cy)  # top
            bounds[2] = max(bounds[2], cx)  # right
            bounds[3] = max(bounds[3], cy)  # bottom

            # Check all neighboring pixels
            for nx, ny in [(cx-1, cy), (cx+1, cy), (cx, cy-1), (cx, cy+1)]:
                if 0 <= nx < width and 0 <= ny < height and not visited[ny][nx]:
                    if img.getpixel((nx, ny))[3] != 0:  # Non-transparent pixel
                        visited[ny][nx] = True
                        queue.append((nx, ny))

    # Identify all sprites and determine the largest sprite size
    max_width, max_height = 0, 0
    for y in range(height):
        for x in range(width):
            if not visited[y][x] and img.getpixel((x, y))[3] != 0:  # Non-transparent and not visited
                bounds = [x, y, x, y]  # left, top, right, bottom
                flood_fill(x, y, bounds)
                left, top, right, bottom = bounds

                if right > left and bottom > top:  # Valid sprite bounds
                    sprite = img.crop((left, top, right + 1, bottom + 1))
                    max_width = max(max_width, right - left + 1)
                    max_height = max(max_height, bottom - top + 1)
                    sprites.append((sprite, left, top, right, bottom))

    # Pad sprites to ensure they are all the same size
    padded_sprites = []
    for sprite, left, top, right, bottom in sprites:
        padded_sprite = Image.new("RGBA", (max_width, max_height), (0, 0, 0, 0))
        sprite_width = right - left + 1
        sprite_height = bottom - top + 1
        padded_sprite.paste(sprite, (0, max_height - sprite_height))  # Anchor to bottom-left
        padded_sprites.append(padded_sprite)

    return padded_sprites


def generate_gif(img, framerate):
    sprites = separate_sprites(img)
    if not sprites:
        raise ValueError("No sprites found in the image.")

    # Create a unique filename using the current timestamp
    timestamp = int(time.time())
    gif_filename = f"output_{timestamp}.gif"
    gif_path = os.path.join("extras-images", gif_filename)  # Save the GIF to a specific directory
    gif_path = os.path.join("output", gif_path)  # Add the "output" folder to the path

    # Determine the size of the GIF based on the largest sprite
    max_width = max(sprite.size[0] for sprite in sprites)
    max_height = max(sprite.size[1] for sprite in sprites)

    frames = []
    for sprite in sprites:
        # Create a blank canvas with transparent background
        frame = Image.new("RGBA", (max_width, max_height), (0, 0, 0, 0))
        
        # Paste the sprite onto the blank canvas, clearing out any previous data
        frame.paste(sprite, (0, max_height - sprite.size[1]))  # Anchor to bottom-left
        frames.append(frame)

    # Ensure that each frame is fully independent
    for i in range(len(frames)):
        frames[i] = frames[i].copy()  # Make sure each frame is a separate image

    # Save the frames as a GIF
    gif = frames[0]
    gif.save(gif_path, save_all=True, append_images=frames[1:], optimize=False, duration=1000//framerate, loop=0, disposal=2)
    
    return gif_path

class ScriptPostprocessingUpscale(scripts_postprocessing.ScriptPostprocessing):
    name = "y4m-pixelizer"
    order = 11000

    def ui(self):
        with ui_components.InputAccordion(False, label="y4m-pixelizer") as enable:
            with gr.Row():
                upscale_after = gr.Checkbox(False, label="Keep resolution")
                pixel_size = gr.Slider(minimum=1, maximum=16, step=1, label="Pixel size", value=8)
                tolerance = gr.Slider(minimum=0, maximum=128, step=1, label="Tolerance", value=12)
            with gr.Row():
                make_gif = gr.Checkbox(False, label="Generate GIF")
                framerate = gr.Slider(minimum=1, maximum=300, step=1, label="Framerate", value=10)

        return {
            "enable": enable,
            "upscale_after": upscale_after,
            "pixel_size": pixel_size,
            "tolerance": tolerance,
            "make_gif": make_gif,
            "framerate": framerate
        }

    def process(self, pp: scripts_postprocessing.PostprocessedImage, enable, upscale_after, pixel_size, tolerance, make_gif, framerate):
        if not enable:
            return

        # Process the image using the simplified image processing function
        processed_image = process_image(pp.image, pixel_size, upscale_after, tolerance)
        
        # Update the PostprocessedImage object with the processed image
        pp.image = processed_image

        if make_gif:
            gif_path = generate_gif(processed_image, framerate)
            pp.info["Generated GIF Path"] = gif_path  # Store the GIF path in pp.info
            pp.image = Image.open(gif_path)  # Optionally load the saved GIF back if needed

            # gif = generate_gif(processed_image, framerate)
            # pp.info["Generated GIF"] = gif  # Add GIF info (or store the GIF path if needed)
            # pp.image = gif

        # Optionally, add some info about the processing
        pp.info["Pixelization pixel size"] = pixel_size

