import cv2
import argparse
import os
import time
from ultralytics import YOLO

def process_video(input_path, model_path, output_path=None, show=True):
    # 1. Load Model
    print(f"⏳ Loading model from {model_path}...")
    model = YOLO(model_path)
    
    # 2. Open Video
    print(f"⏳ Opening video: {input_path}")
    cap = cv2.VideoCapture(input_path)
    if not cap.isOpened():
        print(f"❌ Error: Could not open video file {input_path}")
        return

    # Metadata
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    # 3. Setup Video Writer (Optional)
    writer = None
    if output_path:
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        writer = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
        print(f"💾 Saving output to: {output_path}")

    print(f"🚀 Processing {total_frames} frames... [Press 'q' in the video window to stop early]")
    
    frame_count = 0
    start_time = time.time()

    try:
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            
            frame_count += 1
            
            # Run YOLO Inference (High resolution mode)
            results = model.predict(frame, imgsz=1024, conf=0.15, verbose=False)
            
            # Annotated Frame
            annotated_frame = results[0].plot()
            
            # Calculate metrics
            elapsed_time = time.time() - start_time
            current_fps = frame_count / elapsed_time if elapsed_time > 0 else 0
            
            # Draw overlay on frame
            cv2.putText(annotated_frame, f"Frame: {frame_count}/{total_frames} | FPS: {current_fps:.1f}", 
                        (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)

            # Show results in real-time
            if show:
                cv2.imshow("RoadGuard Standalone Tester", annotated_frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    print("\n🛑 Stopped by user.")
                    break
            
            # Save to file
            if writer:
                writer.write(annotated_frame)
            
            if frame_count % 50 == 0:
                print(f"➡️ Progress: {frame_count}/{total_frames} ({(frame_count/total_frames)*100:.1f}%)")

    except Exception as e:
        print(f"\n❌ Error during processing: {e}")
    finally:
        cap.release()
        if writer:
            writer.release()
        cv2.destroyAllWindows()
        print(f"\n✅ Finished! Success. Total time: {time.time() - start_time:.1f}s")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Standalone YOLO Video Tester")
    parser.add_argument("--input", "-i", type=str, required=True, help="Path to input video file")
    parser.add_argument("--model", "-m", type=str, default="backend/best.pt", help="Path to YOLO .pt model file")
    parser.add_argument("--output", "-o", type=str, help="Path to save annotated video output")
    parser.add_argument("--no-show", action="store_true", help="Disable real-time window display")
    
    args = parser.parse_args()
    
    # Simple dependency check for opencv and ultralytics
    try:
        if not os.path.exists(args.input):
            print(f"❌ Error: Input file '{args.input}' not found.")
        elif not os.path.exists(args.model):
            print(f"❌ Error: Model file '{args.model}' not found.")
        else:
            process_video(args.input, args.model, args.output, not args.no_show)
    except KeyboardInterrupt:
        print("\n🛑 Interrupted by keyboard.")
