"""
Quick-start script for ML training.
Run from the backend directory:

    cd backend
    python run_training.py
"""

import subprocess
import sys
import os

def main():
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(backend_dir)

    print("=" * 72)
    print("  Shelter Thermal Optimizer — ML Training")
    print("=" * 72)

    # Step 1: Install dependencies
    print("\n[1/3] Installing ML dependencies...")
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "-r", "requirements.txt", "-q"],
        check=True,
    )

    # Step 2: Generate training data + train models
    print("\n[2/3] Running ML training pipeline...")
    result = subprocess.run(
        [sys.executable, "-m", "ml.train"],
        cwd=backend_dir,
    )
    if result.returncode != 0:
        print("  Training failed. Check errors above.")
        sys.exit(1)

    # Step 3: Run prediction demo
    print("\n[3/3] Running prediction demo...")
    subprocess.run(
        [sys.executable, "-m", "ml.predict"],
        cwd=backend_dir,
    )

    print("\n" + "=" * 72)
    print("  COMPLETE")
    print("  Models: backend/ml/saved_models/")
    print("  Plots:  backend/ml/plots/")
    print("  Data:   backend/ml/data/")
    print("  API:    POST /api/v1/ml/predict")
    print("=" * 72)


if __name__ == "__main__":
    main()
