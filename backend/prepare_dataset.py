import os
import glob
import shutil
import random
import xml.etree.ElementTree as ET
import cv2

random.seed(42)

BASE_DIR = os.path.join(os.getcwd(), "datasets")
MERGED_DIR = os.path.join(BASE_DIR, "YOLO_merged")

# Create structure
for split in ['train', 'val']:
    os.makedirs(os.path.join(MERGED_DIR, 'images', split), exist_ok=True)
    os.makedirs(os.path.join(MERGED_DIR, 'labels', split), exist_ok=True)

def get_split():
    return 'train' if random.random() < 0.8 else 'val'

# Process Dataset 1: pothole-detection (PASCAL VOC -> YOLO)
ds1_dir = os.path.join(BASE_DIR, "pothole-detection")
if os.path.exists(ds1_dir):
    print("Processing Dataset 1 (pothole-detection)...")
    xml_files = glob.glob(os.path.join(ds1_dir, "annotations", "*.xml"))
    for xml_file in xml_files:
        tree = ET.parse(xml_file)
        root = tree.getroot()
        
        filename = root.find('filename').text
        image_path = os.path.join(ds1_dir, "images", filename)
        if not os.path.exists(image_path):
            continue
            
        size = root.find('size')
        if size is None: continue
        w_img = int(size.find('width').text)
        h_img = int(size.find('height').text)
        
        if w_img == 0 or h_img == 0:
            # Fallback
            img = cv2.imread(image_path)
            if img is not None:
                h_img, w_img = img.shape[:2]
            else:
                continue

        split = get_split()
        dest_img_path = os.path.join(MERGED_DIR, 'images', split, f"ds1_{filename}")
        shutil.copy(image_path, dest_img_path)
        
        dest_label_path = os.path.join(MERGED_DIR, 'labels', split, f"ds1_{os.path.splitext(filename)[0]}.txt")
        with open(dest_label_path, 'w') as f_out:
            for obj in root.findall('object'):
                name = obj.find('name').text
                if name == 'pothole':
                    class_id = 0
                else:
                    continue # Skip other classes for now
                    
                bndbox = obj.find('bndbox')
                xmin = float(bndbox.find('xmin').text)
                ymin = float(bndbox.find('ymin').text)
                xmax = float(bndbox.find('xmax').text)
                ymax = float(bndbox.find('ymax').text)
                
                # Convert to YOLO
                x_center = ((xmin + xmax) / 2) / w_img
                y_center = ((ymin + ymax) / 2) / h_img
                w_bbox = (xmax - xmin) / w_img
                h_bbox = (ymax - ymin) / h_img
                
                f_out.write(f"{class_id} {x_center:.6f} {y_center:.6f} {w_bbox:.6f} {h_bbox:.6f}\n")

# Process Dataset 3: road-damage-dataset...
ds3_dir = os.path.join(BASE_DIR, "road-damage-dataset-potholes-cracks-and-manholes", "data")
if os.path.exists(ds3_dir):
    print("Processing Dataset 3 (road-damage-dataset)...")
    images_dir = os.path.join(ds3_dir, "images")
    labels_dir = os.path.join(ds3_dir, "labels-YOLO")
    
    img_files = glob.glob(os.path.join(images_dir, "*"))
    for img_path in img_files:
        filename = os.path.basename(img_path)
        base_name = os.path.splitext(filename)[0]
        label_path = os.path.join(labels_dir, f"{base_name}.txt")
        
        if not os.path.exists(label_path):
            continue
            
        split = get_split()
        dest_img_path = os.path.join(MERGED_DIR, 'images', split, f"ds3_{filename}")
        shutil.copy(img_path, dest_img_path)
        
        dest_label_path = os.path.join(MERGED_DIR, 'labels', split, f"ds3_{base_name}.txt")
        shutil.copy(label_path, dest_label_path)

# Process Dataset 2: Background Images (normal roads)
ds2_dir = os.path.join(BASE_DIR, "pothole-detection-dataset", "normal")
if os.path.exists(ds2_dir):
    print("Processing Dataset 2 (Background images - normal roads)...")
    img_files = glob.glob(os.path.join(ds2_dir, "*"))
    for img_path in img_files:
        filename = os.path.basename(img_path)
        split = get_split()
        dest_img_path = os.path.join(MERGED_DIR, 'images', split, f"bg_{filename}")
        shutil.copy(img_path, dest_img_path)
        # Background images do NOT get a label text file!

# Create data.yaml
yaml_content = f"""path: {MERGED_DIR}
train: images/train
val: images/val

names:
  0: pothole
  1: crack
  2: manhole
"""
with open(os.path.join(MERGED_DIR, "data.yaml"), "w") as f:
    f.write(yaml_content)

print("Dataset merging and formatting complete!")
print(f"Dataset is ready at: {MERGED_DIR}/data.yaml")
