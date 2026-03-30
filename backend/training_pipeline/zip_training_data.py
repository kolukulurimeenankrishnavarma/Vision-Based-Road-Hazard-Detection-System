import os
import zipfile

def zip_directory(folder_path, zip_file):
    for root, dirs, files in os.walk(folder_path):
        for file in files:
            file_path = os.path.join(root, file)
            # Add file to zip relative to the parent of folder_path
            arcname = os.path.relpath(file_path, start=os.path.dirname(folder_path))
            zip_file.write(file_path, arcname)

output_zip = "RoadGuard_Training_Data.zip"

print(f"Creating {output_zip}...")
with zipfile.ZipFile(output_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
    
    # 1. Add the dataset
    dataset_path = os.path.join("datasets", "YOLO_merged")
    if os.path.exists(dataset_path):
        print("Adding YOLO_merged dataset...")
        zip_directory(dataset_path, zipf)
    else:
        print(f"Warning: {dataset_path} not found.")

    # 2. Add the training script
    if os.path.exists("train_model.py"):
        print("Adding train_model.py...")
        zipf.write("train_model.py", "train_model.py")
        
    # 3. Add the initial model
    # The default yolo model we used was called best.pt but wait, is it in the backend folder?
    model_path = os.getenv("YOLO_MODEL_PATH", "best.pt")
    if os.path.exists(model_path):
        print(f"Adding initial weight file {model_path}...")
        zipf.write(model_path, os.path.basename(model_path))
    # Check parent dir just in case
    elif os.path.exists(os.path.join("..", "best.pt")):
        print("Adding initial weight file ../best.pt...")
        zipf.write(os.path.join("..", "best.pt"), "best.pt")
        
print("Done! All files successfully packaged into:", output_zip)
