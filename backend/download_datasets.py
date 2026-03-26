import os
import subprocess

DATASETS = [
    "andrewmvd/pothole-detection",
    "atulyakumar98/pothole-detection-dataset",
    "lorenzoarcioni/road-damage-dataset-potholes-cracks-and-manholes",
    "albertoefontalvop/pothole-dataset"
]

BASE_DIR = os.path.join(os.getcwd(), "datasets")
os.makedirs(BASE_DIR, exist_ok=True)

for i, dataset in enumerate(DATASETS):
    folder_name = dataset.split("/")[-1]
    target_dir = os.path.join(BASE_DIR, folder_name)
    os.makedirs(target_dir, exist_ok=True)
    
    print(f"[{i+1}/{len(DATASETS)}] Downloading {dataset} into {target_dir}...")
    
    cmd = f"kaggle datasets download -d {dataset} -p \"{target_dir}\" --unzip"
    
    try:
        subprocess.run(cmd, check=True, shell=True)
        print(f"Successfully downloaded and unzipped {dataset}.")
    except subprocess.CalledProcessError as e:
        print(f"Failed to download {dataset}: {e}")

print("All datasets processed.")
