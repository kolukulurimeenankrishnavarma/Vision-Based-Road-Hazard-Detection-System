import sys
import qrcode
from pyngrok import ngrok

def main():
    print("Starting ngrok tunnel on port 8000...")
    try:
        # Open a HTTP tunnel to local port 8000
        public_url = ngrok.connect(8000)
        url_str = public_url.public_url
        print("\n" + "=" * 60)
        print(f"🌍 ROADGUARD PUBLIC URL: {url_str}")
        print("Share this link with anyone to access RoadGuard from anywhere!")
        print("=" * 60 + "\n")
        
        # Generate and print QR Code to the terminal
        print("📱 Scan this QR code with your phone:\n")
        qr = qrcode.QRCode(version=1, box_size=10, border=2)
        qr.add_data(url_str)
        qr.make(fit=True)
        qr.print_ascii(tty=True)
        
        print("\nLeave this window open. Press Ctrl+C to close the tunnel.")

        
        # Block until CTRL-C or some other terminating event
        ngrok_process = ngrok.get_ngrok_process()
        ngrok_process.proc.wait()
    except Exception as e:
        print(f"Failed to start ngrok: {e}")
        print("If you haven't authenticated, run: ngrok config add-authtoken <your-token>")
    except KeyboardInterrupt:
        print("\nShutting down ngrok tunnel...")
        ngrok.kill()

if __name__ == "__main__":
    main()
