
from app import app

if __name__ == "__main__":
    # Use port 5000 to match deployment settings
    app.run(host="0.0.0.0", port=5000, debug=True)
