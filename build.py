"""
Build script for creating Windows EXE using PyInstaller.
Run: python build.py
"""

import subprocess
import sys
from pathlib import Path


def main():
    # Check PyInstaller is installed
    try:
        import PyInstaller
    except ImportError:
        print("Installing PyInstaller...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])

    # Build command
    script_dir = Path(__file__).parent

    # Path separator: ; on Windows, : on Linux/Mac
    import platform
    sep = ";" if platform.system() == "Windows" else ":"


    # [cite_start]請確保 hacker.ico 存在，若只有 png 請先轉檔 [cite: 2]
    # 在 build_final.py 的 cmd 清單中加入 hidden-import
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name=HackerMusic",
        "--onefile",
        "--windowed",
        "--clean",
        f"--add-data={script_dir / 'client.html'}{sep}.",
        "--add-data=client.html;.",
        "--add-data=server.py;.",
        "--add-data=hacker.jpg;.",
        "--icon=hacker.png",
        "--hidden-import=websockets",        # 💡 強制包含 WebSocket 支援
        "--hidden-import=uvicorn.protocols.websockets.websockets_impl", # 💡 修正封裝路徑
        str(script_dir / "hacker_music.py")
    ]
    print("Building AudioStream.exe...")
    print("This may take a few minutes...")
    print()

    subprocess.run(cmd)

    print()
    print("=" * 50)
    print("Build complete!")
    print(f"EXE location: {script_dir / 'dist' / 'AudioStream.exe'}")
    print("=" * 50)
if __name__ == "__main__":
    main()