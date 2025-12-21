import os
import math
import argparse
import re
from PIL import Image, ImageOps, ImageDraw, ImageFilter, ImageSequence
from tqdm import tqdm # For a nice progress bar

# --- Configuration ---
BASE_FOLDER = "img"
SOURCE_FOLDER = os.path.join(BASE_FOLDER, "_ORG")
MAX_WIDTH = 800
QUALITY = 45  # Reduced to 45 for tighter compression
BG_REMOVAL_TOLERANCE = 20 
BG_SAMPLE_SIZE = 10 
BG_MATCH_THRESHOLD = 20 

AVIF_SUBFOLDER = os.path.join(BASE_FOLDER, "avif")
WEBP_SUBFOLDER = os.path.join(BASE_FOLDER, "webp")
JPEG_SUBFOLDER = os.path.join(BASE_FOLDER, "jpeg")
GIF_SUBFOLDER = os.path.join(BASE_FOLDER, "gif") # New folder for optimized GIFs
# --- End Configuration ---

def get_avg_color(img, box):
    """Calculates the average color of a region."""
    region = img.crop(box)
    avg_pixel = region.resize((1, 1), Image.Resampling.BOX).getpixel((0, 0))
    return avg_pixel

def color_distance(c1, c2):
    """Calculates Euclidean distance between two RGB(A) colors."""
    r_diff = c1[0] - c2[0]
    g_diff = c1[1] - c2[1]
    b_diff = c1[2] - c2[2]
    return math.sqrt(r_diff**2 + g_diff**2 + b_diff**2)

def optimize_and_convert(force=False, remove_bg=False, specific_file=None, custom_width=None):
    """
    Resizes, compresses, and converts images. 
    Handles Animations (GIF/WebP) and Static images differently.
    """
    
    os.makedirs(AVIF_SUBFOLDER, exist_ok=True)
    os.makedirs(WEBP_SUBFOLDER, exist_ok=True)
    os.makedirs(JPEG_SUBFOLDER, exist_ok=True)
    os.makedirs(GIF_SUBFOLDER, exist_ok=True)

    print(f"Source folder: {SOURCE_FOLDER}")
    print(f"Output folders: {AVIF_SUBFOLDER}, {WEBP_SUBFOLDER}, {JPEG_SUBFOLDER}, {GIF_SUBFOLDER}")
    
    supported_extensions = ('.jpg', '.jpeg', '.png', '.webp', '.gif') 
    
    all_files_paths = []

    if specific_file:
        # Check if specific file exists
        if os.path.exists(specific_file) and os.path.isfile(specific_file):
            all_files_paths = [specific_file]
        # Check if it exists inside source folder
        elif os.path.exists(os.path.join(SOURCE_FOLDER, specific_file)):
             all_files_paths = [os.path.join(SOURCE_FOLDER, specific_file)]
        else:
             print(f"Error: File '{specific_file}' not found.")
             return
    else:
        if not os.path.exists(SOURCE_FOLDER):
             print(f"Source folder '{SOURCE_FOLDER}' does not exist.")
             return

        files_in_dir = [f for f in os.listdir(SOURCE_FOLDER) 
                     if f.lower().endswith(supported_extensions) and os.path.isfile(os.path.join(SOURCE_FOLDER, f))]

        if not files_in_dir:
            print(f"No valid images found in '{SOURCE_FOLDER}'.")
            return
            
        all_files_paths = [os.path.join(SOURCE_FOLDER, f) for f in files_in_dir]

    print(f"Found {len(all_files_paths)} images to process.")

    # Pre-calculate stem counts for collision handling (only relevant if processing batch from source, 
    # but harmless to do for single file too, though mostly 1)
    stem_counts = {}
    for path in all_files_paths:
        f_name = os.path.basename(path)
        stem = os.path.splitext(f_name)[0].lower()
        stem_counts[stem] = stem_counts.get(stem, 0) + 1

    for input_path in tqdm(all_files_paths, desc="Processing Images"):
        filename = os.path.basename(input_path)
        
        try:
            original_size = os.path.getsize(input_path)
        except OSError:
            original_size = 0

        stem = os.path.splitext(filename)[0]
        if stem_counts.get(stem.lower(), 0) > 1:
             ext = os.path.splitext(filename)[1]
             base_name = f"{stem}{ext.replace('.', '_')}"
        else:
             base_name = stem

        webp_output_path = os.path.join(WEBP_SUBFOLDER, base_name + ".webp")
        avif_output_path = os.path.join(AVIF_SUBFOLDER, base_name + ".avif")
        jpeg_output_path = os.path.join(JPEG_SUBFOLDER, base_name + ".jpg")
        gif_output_path = os.path.join(GIF_SUBFOLDER, base_name + ".gif")
        
        # --- Determine Max Width ---
        if custom_width:
             current_max_width = custom_width
        else:
            current_max_width = MAX_WIDTH
            match = re.search(r'(\d+)$', stem)
            if match:
                 try:
                     val = int(match.group(1))
                     if 100 <= val <= 10000:
                         current_max_width = val
                 except ValueError:
                     pass
        
        # --- Smart Check: Skip if all exist ---
        # For GIFs, we check all 4. For others, we check WebP, AVIF, JPEG.
        is_gif_input = filename.lower().endswith('.gif')
        
        if force:
            webp_exists = False
            avif_exists = False
            jpeg_exists = False
            gif_exists = False
        else:
            webp_exists = os.path.exists(webp_output_path)
            avif_exists = os.path.exists(avif_output_path)
            jpeg_exists = os.path.exists(jpeg_output_path)
            gif_exists = os.path.exists(gif_output_path)

        if is_gif_input:
            if webp_exists and avif_exists and jpeg_exists and gif_exists:
                tqdm.write(f"⏭️  Skipping {filename} (All formats exist)")
                continue
        else:
            if webp_exists and avif_exists and jpeg_exists:
                tqdm.write(f"⏭️  Skipping {filename} (All formats exist)")
                continue

        # If we are here, something is missing.
        missing_formats = []
        if not webp_exists: missing_formats.append("WebP")
        if not avif_exists: missing_formats.append("AVIF")
        if not jpeg_exists: missing_formats.append("JPEG")
        if is_gif_input and not gif_exists: missing_formats.append("GIF")
        
        tqdm.write(f"⚙️  Processing {filename}. Missing: {', '.join(missing_formats)}")

        try:
            with Image.open(input_path) as img:
                
                # Check for Animation
                is_animated = getattr(img, "is_animated", False) and img.n_frames > 1

                if is_animated:
                    # --- Animation Path ---
                    frames = []
                    duration = img.info.get('duration', 100)
                    loop = img.info.get('loop', 0)

                    # Only load frames if we actually need to generate something animated or the static frame
                    # But since we need frames for everything, we just load them.
                    
                    for frame in ImageSequence.Iterator(img):
                        frame = frame.convert("RGBA")
                        
                        # Resize Frame
                        original_width, original_height = frame.size
                        if original_width > current_max_width:
                            new_height = int((current_max_width / original_width) * original_height)
                            frame = frame.resize((current_max_width, new_height), Image.Resampling.LANCZOS)
                        
                        # --- Clean Alpha ---
                        datas = frame.getdata()
                        new_data = []
                        has_transparency = False
                        for item in datas:
                            if item[3] == 0:
                                new_data.append((0, 0, 0, 0))
                                has_transparency = True
                            else:
                                new_data.append(item)
                        
                        if has_transparency:
                            frame.putdata(new_data)

                        frames.append(frame)

                    if not frames: continue

                    # 1. Save Animated WebP
                    if not webp_exists:
                        frames[0].save(webp_output_path, format='WEBP',
                                       save_all=True, append_images=frames[1:],
                                       optimize=True, quality=QUALITY, duration=duration, loop=loop,
                                       method=6)

                    # 2. Save Animated AVIF
                    if not avif_exists:
                        try:
                            frames[0].save(avif_output_path, format='AVIF',
                                           save_all=True, append_images=frames[1:],
                                           quality=QUALITY, duration=duration, loop=loop)
                        except Exception:
                            pass 

                    # 3. Save Optimized GIF
                    if not gif_exists:
                        gif_frames = [f.convert('P', palette=Image.Palette.ADAPTIVE) for f in frames]
                        gif_frames[0].save(gif_output_path, format='GIF',
                                           save_all=True, append_images=gif_frames[1:],
                                           optimize=True, duration=duration, loop=loop)

                    # 4. Save Static JPEG (Frame 0)
                    if not jpeg_exists:
                        first_frame_rgb = frames[0].convert("RGB")
                        first_frame_rgb.save(jpeg_output_path, 'jpeg', 
                                             quality=QUALITY, optimize=True, progressive=True, subsampling=2)
                    
                    # Sizes for report
                    webp_size = os.path.getsize(webp_output_path) if os.path.exists(webp_output_path) else 0
                    gif_size = os.path.getsize(gif_output_path) if os.path.exists(gif_output_path) else 0
                    
                    tqdm.write(f"   Done. Orig: {original_size/1024:.1f} KB")

                else:
                    # --- Static Image Path ---
                    img = ImageOps.exif_transpose(img)
                    original_width, original_height = img.size
                    if original_width > current_max_width:
                        new_height = int((current_max_width / original_width) * original_height)
                        img = img.resize((current_max_width, new_height), Image.Resampling.LANCZOS)

                    if not jpeg_exists:
                        if img.mode != 'RGB':
                            img_jpeg = img.convert('RGB')
                        else:
                            img_jpeg = img.copy()

                        img_jpeg.save(jpeg_output_path, 'jpeg', 
                                      quality=QUALITY, 
                                      optimize=True, 
                                      progressive=True,
                                      subsampling=2)

                    # Only do background removal and complex processing if we need WebP or AVIF
                    if not webp_exists or not avif_exists:
                        img_trans = img.convert("RGBA")
                        if remove_bg:
                            w, h = img_trans.size
                            s = BG_SAMPLE_SIZE
                            
                            corners = [
                                (0, 0, s, s),                 # TL
                                (w-s, 0, w, s),               # TR
                                (0, h-s, s, h),               # BL
                                (w-s, h-s, w, h)              # BR
                            ]
                            
                            corner_points = [(0,0), (w-1, 0), (0, h-1), (w-1, h-1)] 
                            
                            corner_colors = []
                            for box in corners:
                                corner_colors.append(get_avg_color(img_trans, box))
                            
                            bg_detected = False
                            matching_indices = []
                            
                            for i in range(len(corner_colors)):
                                current_matches = [i]
                                for j in range(len(corner_colors)):
                                    if i == j: continue
                                    if color_distance(corner_colors[i], corner_colors[j]) < BG_MATCH_THRESHOLD:
                                        current_matches.append(j)
                                
                                if len(current_matches) >= 3:
                                    bg_detected = True
                                    matching_indices = current_matches
                                    break
                            
                            if bg_detected:
                                tqdm.write(f"   ✨ Plain background detected. Removing and cleaning edges...")
                                for idx in matching_indices:
                                    seed = corner_points[idx]
                                    ImageDraw.floodfill(img_trans, seed, (0, 0, 0, 0), thresh=BG_REMOVAL_TOLERANCE)
                                
                                alpha = img_trans.getchannel('A')
                                alpha = alpha.filter(ImageFilter.MinFilter(3))
                                img_trans.putalpha(alpha)

                        if not webp_exists:
                            img_trans.save(webp_output_path, 'webp', 
                                     quality=QUALITY, 
                                     lossless=False, 
                                     method=6)
                        
                        if not avif_exists:
                            img_trans.save(avif_output_path, 'avif', 
                                     quality=QUALITY,
                                     chroma=420)

                    # Reporting
                    webp_size = os.path.getsize(webp_output_path) if os.path.exists(webp_output_path) else 0
                    avif_size = os.path.getsize(avif_output_path) if os.path.exists(avif_output_path) else 0
                    jpeg_size = os.path.getsize(jpeg_output_path) if os.path.exists(jpeg_output_path) else 0
                    
                    def get_ratio_str(new_size, old_size):
                        if old_size == 0: return "N/A"
                        percent = (new_size / old_size) * 100
                        return f"{percent:.1f}%"

                    tqdm.write(f"   Done. Orig: {original_size/1024:.1f} KB")
                    if not webp_exists: tqdm.write(f"   + WebP: {webp_size/1024:.1f} KB ({get_ratio_str(webp_size, original_size)})")
                    if not avif_exists: tqdm.write(f"   + AVIF: {avif_size/1024:.1f} KB ({get_ratio_str(avif_size, original_size)})")
                    if not jpeg_exists: tqdm.write(f"   + JPEG: {jpeg_size/1024:.1f} KB ({get_ratio_str(jpeg_size, original_size)})")
                
        except Exception as e:
            tqdm.write(f"\n[ERROR] Failed to process {filename}: {e}")

    print("\n✅ Image optimization complete!")
    print(f"Check the '{WEBP_SUBFOLDER}', '{AVIF_SUBFOLDER}', '{JPEG_SUBFOLDER}', and '{GIF_SUBFOLDER}' folders.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Optimize and convert images.")
    parser.add_argument("--force", action="store_true", help="Force regeneration of all images.")
    parser.add_argument("--remove-bg", action="store_true", help="Enable background removal.")
    parser.add_argument("--file", type=str, help="Specific file to process.")
    parser.add_argument("--ts", type=int, help="Custom target width (overrides default/filename width).")
    args = parser.parse_args()
    optimize_and_convert(force=args.force, remove_bg=args.remove_bg, specific_file=args.file, custom_width=args.ts)
