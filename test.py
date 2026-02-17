from PIL import Image

# 讀取你的 jpg 檔案
img = Image.open("hacker.jpg")

# 轉換成 ico 格式，並包含多種尺寸以適應 Windows 縮放
# 建議尺寸：16x16, 32x32, 48x48, 64x64, 128x128, 256x256
img.save("hacker.ico", format="ICO", sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])

print("成功將 jpg 轉換為 hacker.ico！")