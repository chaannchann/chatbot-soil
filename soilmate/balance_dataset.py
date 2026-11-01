import os
import random
import shutil
from PIL import Image, ImageEnhance

# Source path where your 9 folders are located
SOURCE_DIR = r"C:\Users\joshua\Downloads\soil dataset\Dataset\test"
OUTPUT_DIR = r"./data/balanced_dataset"

TARGET_COUNT = 200
TRAIN_RATIO = 0.8  # 160 train, 40 test per class

# The 9 classes
CLASSES = [
    "Alluvial soil",
    "Clay soil",
    "Cinder Soil",
    "Peat Soil",
    "Black Soil",
    "Laterite Soil",
    "Red soil",
    "Yellow Soil",
    "soil with algae",
    "concrete surface"
]

def augment_image(img):
    """Generate realistic variations of soil and surface textures."""
    transforms = [
        lambda i: i.transpose(Image.ROTATE_90),
        lambda i: i.transpose(Image.ROTATE_180),
        lambda i: i.transpose(Image.ROTATE_270),
        lambda i: i.transpose(Image.FLIP_LEFT_RIGHT),
        lambda i: i.transpose(Image.FLIP_TOP_BOTTOM),
        lambda i: ImageEnhance.Brightness(i).enhance(random.uniform(0.85, 1.15)),
        lambda i: ImageEnhance.Contrast(i).enhance(random.uniform(0.85, 1.15)),
    ]
    return random.choice(transforms)(img)

def process_dataset():
    random.seed(42)
    
    # Wipe old balanced data to ensure clean generation
    if os.path.exists(OUTPUT_DIR):
        shutil.rmtree(OUTPUT_DIR)

    for split in ["train", "test"]:
        for cls in CLASSES:
            clean_cls_name = cls.replace(" ", "_")
            os.makedirs(os.path.join(OUTPUT_DIR, split, clean_cls_name), exist_ok=True)

    print(f"--- Balancing all 9 classes to {TARGET_COUNT} images each ---")

    for cls in CLASSES:
        clean_cls_name = cls.replace(" ", "_")
        src_path = os.path.join(SOURCE_DIR, cls)
        
        if not os.path.exists(src_path):
            print(f"⚠️ Warning: Folder not found: {src_path}")
            continue

        valid_files = [
            f for f in os.listdir(src_path) 
            if f.lower().endswith(('.jpg', '.jpeg', '.png'))
        ]

        loaded_images = []
        # Case A: >= 200 images (Downsample)
        if len(valid_files) >= TARGET_COUNT:
            selected_files = random.sample(valid_files, TARGET_COUNT)
            for fname in selected_files:
                img_path = os.path.join(src_path, fname)
                try:
                    with Image.open(img_path) as img:
                        loaded_images.append(img.convert('RGB'))
                except Exception:
                    continue

        # Case B: < 200 images (Augment up to 200)
        else:
            for fname in valid_files:
                img_path = os.path.join(src_path, fname)
                try:
                    with Image.open(img_path) as img:
                        loaded_images.append(img.convert('RGB'))
                except Exception:
                    continue
            
            original_pool = list(loaded_images)
            while len(loaded_images) < TARGET_COUNT and original_pool:
                base_img = random.choice(original_pool)
                aug_img = augment_image(base_img)
                loaded_images.append(aug_img)

        # Split into 80% train (160), 20% test (40)
        random.shuffle(loaded_images)
        train_count = int(TARGET_COUNT * TRAIN_RATIO)
        train_imgs = loaded_images[:train_count]
        test_imgs = loaded_images[train_count:TARGET_COUNT]

        for idx, img in enumerate(train_imgs):
            save_path = os.path.join(OUTPUT_DIR, "train", clean_cls_name, f"{clean_cls_name}_train_{idx+1}.jpg")
            img.save(save_path, "JPEG")

        for idx, img in enumerate(test_imgs):
            save_path = os.path.join(OUTPUT_DIR, "test", clean_cls_name, f"{clean_cls_name}_test_{idx+1}.jpg")
            img.save(save_path, "JPEG")

        print(f"[{clean_cls_name}] -> Train: {len(train_imgs)}, Test: {len(test_imgs)} (Total: {TARGET_COUNT})")

    print(f"\nAll classes balanced! Saved to {OUTPUT_DIR}")

if __name__ == "__main__":
    process_dataset()