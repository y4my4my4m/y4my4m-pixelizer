import os
import gradio as gr
from modules import scripts_postprocessing, devices, scripts, ui_components
from modules.ui_components import FormRow
from PIL import Image

def is_within_tolerance(pixel, reference_pixel, tolerance):
    return all(abs(pixel[i] - reference_pixel[i]) <= tolerance for i in range(3))  # Compare RGB channels only

def process_image(img, pixel_size, upscale_after, tolerance):
    # Scale down the image by the pixel size using nearest neighbor
    width, height = img.size
    scaled_width = width // pixel_size
    scaled_height = height // pixel_size

    img = img.resize((scaled_width, scaled_height), Image.Resampling.NEAREST)

    if (tolerance != 0):
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

class ScriptPostprocessingUpscale(scripts_postprocessing.ScriptPostprocessing):
    name = "y4m-pixelizer"
    order = 11000

    def ui(self):
        with ui_components.InputAccordion(False, label="y4m-pixelizer") as enable:
            with gr.Row():
                upscale_after = gr.Checkbox(False, label="Keep resolution")
                pixel_size = gr.Slider(minimum=1, maximum=16, step=1, label="Pixel size", value=8)
                tolerance = gr.Slider(minimum=0, maximum=128, step=1, label="Tolerance", value=12)

        return {
            "enable": enable,
            "upscale_after": upscale_after,
            "pixel_size": pixel_size,
            "tolerance": tolerance
        }

    def process(self, pp: scripts_postprocessing.PostprocessedImage, enable, upscale_after, pixel_size, tolerance):
        if not enable:
            return

        # Process the image using the simplified image processing function
        processed_image = process_image(pp.image, pixel_size, upscale_after, tolerance)
        
        # Update the PostprocessedImage object with the processed image
        pp.image = processed_image

        # Optionally, add some info about the processing
        pp.info["Pixelization pixel size"] = pixel_size

