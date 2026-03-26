from ultralytics import YOLO
import argparse
import os

def train_model(model_path, data_yaml_path, epochs, batch_size, imgsz):
    # Load the existing model (e.g., best.pt)
    if not os.path.exists(model_path):
        print(f"Error: Model not found at {model_path}")
        return

    if not os.path.exists(data_yaml_path):
        print(f"Error: Dataset yaml not found at {data_yaml_path}")
        return

    print(f"Loading model from {model_path}...")
    model = YOLO(model_path)

    print(f"Starting training on {data_yaml_path} for {epochs} epochs...")
    results = model.train(
        data=data_yaml_path,
        epochs=epochs,
        batch=batch_size,
        imgsz=imgsz,
        # You can resume from a previously interrupted run:
        # resume=True 
    )

    print("Training complete! The new best model will be saved in the 'runs/detect/train/weights' directory.")
    
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train RoadGuard YOLOv8 model further")
    parser.add_argument("--model", type=str, default="best.pt", help="Path to the initial model weights (best.pt)")
    parser.add_argument("--data", type=str, required=True, help="Path to the dataset data.yaml file")
    parser.add_argument("--epochs", type=int, default=50, help="Number of epochs to train")
    parser.add_argument("--batch", type=int, default=16, help="Batch size")
    parser.add_argument("--imgsz", type=int, default=640, help="Image size")
    
    args = parser.parse_args()
    
    train_model(args.model, args.data, args.epochs, args.batch, args.imgsz)
