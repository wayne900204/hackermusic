# Hacker Music

Stream audio from your Windows PC to any device over WiFi.

## Features

- 🎵 **High Quality**: 48kHz stereo audio
- ⚡ **Low Latency**: ~50-150ms
- 📱 **No App Required**: Works in any browser
- 🔗 **Easy Connect**: QR code for quick connecting

## Quick Start

### Install & Run

```bash
pip install -r requirements.txt
python hacker_music.py
```

### Connect Your Device

1. Open the URL shown in the app (or scan QR code)
2. Tap **"Start Audio"**
3. Done! 🎉

## Requirements

- Windows 10/11
- Python 3.8+
- VB-Cable or Stereo Mix enabled
- Same WiFi network for all devices

## Building Executables

```bash
python build.py       # CustomTkinter version
```

## Troubleshooting

**No audio captured?**
- Install [VB-Cable](https://vb-audio.com/Cable/) (recommended)
- Or enable Stereo Mix in Windows Sound settings

**Can't connect?**
- Check both devices are on same WiFi
- Allow Python through Windows Firewall
