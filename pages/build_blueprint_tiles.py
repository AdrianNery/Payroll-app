# build_blueprint_tiles.py

import math
import io
import fitz  # PyMuPDF
from PIL import Image
from supabase import create_client, Client
import requests
import uuid
import json
from datetime import datetime

# -------------------------
# CONFIG: fill these in
# -------------------------
SUPABASE_URL = "https://YOUR-project-id.supabase.co"
SUPABASE_SERVICE_ROLE_KEY = "YOUR_SERVICE_ROLE_KEY"  # use service key for upload/insert server-side
BUCKET_NAME = "blueprints"

TILE_SIZE = 256        # pixels per tile
OUTPUT_MAX_ZOOM = 5    # how deep we generate zoom levels (0..5)
JOB_NAME = "Mainline Phase 1"  # human label for this upload

PDF_PATH = "job.pdf"   # <-- path to the multi-page blueprint set you got

# -------------------------
# helpers
# -------------------------

def render_pdf_pages(pdf_path, dpi=300):
    """
    Render each page of the PDF to a PIL.Image at a given DPI.
    Returns list[Image].
    """
    doc = fitz.open(pdf_path)
    images = []

    for page in doc:
        zoom = dpi / 72.0  # PDF is 72dpi native
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        images.append(img)

    return images

def stitch_pages_side_by_side(pages, cols=5):
    """
    Very first pass: lay pages in a grid (cols wide).
    Later you can control exact placement based on stationing / matchlines.
    """
    if not pages:
        raise ValueError("No pages to stitch")

    w = max(p.width for p in pages)
    h = max(p.height for p in pages)

    # grid math
    rows = math.ceil(len(pages) / cols)

    total_w = cols * w
    total_h = rows * h

    big = Image.new("RGB", (total_w, total_h), (255, 255, 255))

    for idx, page_img in enumerate(pages):
        row = idx // cols
        col = idx % cols
        x = col * w
        y = row * h
        big.paste(page_img, (x, y))

    return big

def generate_zoom_levels(base_img, max_zoom):
    """
    max_zoom = biggest, most detailed level.
    zoom 0 = smallest.
    We'll downscale for lower zooms.
    Return dict[int zoom_level -> PIL.Image]
    """
    zoom_levels = {}
    zoom_levels[max_zoom] = base_img

    # generate smaller zooms
    for z in range(max_zoom - 1, -1, -1):
        prev = zoom_levels[z + 1]
        w, h = prev.size
        img = prev.resize((w // 2, h // 2), Image.BILINEAR)
        zoom_levels[z] = img

    return zoom_levels

def slice_into_tiles(img, tile_size):
    """
    Break one zoom level image into { (tx,ty): tile_image }
    """
    tiles = {}
    w, h = img.size
    tiles_x = math.ceil(w / tile_size)
    tiles_y = math.ceil(h / tile_size)

    for ty in range(tiles_y):
        for tx in range(tiles_x):
            left = tx * tile_size
            upper = ty * tile_size
            right = min(left + tile_size, w)
            lower = min(upper + tile_size, h)
            tile = img.crop((left, upper, right, lower))
            tiles[(tx, ty)] = tile
    return tiles

def upload_tile(supabase: Client, bucket, path, pil_img):
    """
    Upload a PNG tile to Supabase Storage at {path}
    """
    buf = io.BytesIO()
    pil_img.save(buf, format="PNG")
    buf.seek(0)
    # Supabase Python client <-> storage API
    res = supabase.storage.from_(bucket).upload(
        path=path,
        file=buf,
        file_options={"content-type": "image/png", "upsert": True}
    )
    return res

def insert_job_row(supabase: Client, job_name, tile_base_path, max_zoom_level):
    """
    Create row in blueprint_jobs and return that row (including the id).
    """
    data = {
        "job_name": job_name,
        "tile_base_path": tile_base_path,
        "max_zoom_level": max_zoom_level,
    }
    resp = supabase.table("blueprint_jobs").insert(data).execute()
    if not resp.data:
        raise RuntimeError(f"Failed to insert job row: {resp}")
    return resp.data[0]

def main():
    # connect to supabase
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

    # 1. render PDF pages to images
    pages = render_pdf_pages(PDF_PATH, dpi=300)

    # 2. stitch pages into one giant canvas
    stitched = stitch_pages_side_by_side(pages, cols=5)
    full_w, full_h = stitched.size
    print("Stitched size:", full_w, "x", full_h)

    # 3. create DB job row first so we know job_id for path
    # we'll store tiles under blueprints/job_<job_id>/
    temp_fake_path = "blueprints/temp"  # placeholder
    job_row = insert_job_row(
        supabase,
        JOB_NAME,
        temp_fake_path,
        OUTPUT_MAX_ZOOM
    )
    job_id = job_row["id"]

    tile_base_path = f"blueprints/job_{job_id}"
    print("job_id:", job_id)
    print("tile_base_path:", tile_base_path)

    # update the row with correct path now that we know it
    supabase.table("blueprint_jobs").update({
        "tile_base_path": tile_base_path
    }).eq("id", job_id).execute()

    # 4. build zoom stack
    zoom_imgs = generate_zoom_levels(stitched, OUTPUT_MAX_ZOOM)

    # 5. slice each zoom level into tiles and upload
    for zoom_level, zimg in zoom_imgs.items():
        tiles = slice_into_tiles(zimg, TILE_SIZE)
        for (tx, ty), tile_img in tiles.items():
            storage_path = f"{tile_base_path}/{zoom_level}/{tx}_{ty}.png"
            upload_tile(supabase, BUCKET_NAME, storage_path, tile_img)

    print("Done. Your tiles are in Supabase Storage and blueprint_jobs is populated.")
    print("Record in blueprint_jobs:")
    print(job_row)

if __name__ == "__main__":
    main()