# Gladiator Idle Manager

Hyper-casual idle game — manage gladiators, fight in the arena, earn gold while offline.

## Features
- Arena battles with tier progression
- Gladiator roster — hire, upgrade, select active fighter
- Idle gold income with offline earnings
- Shop with boosts, healing, and stat scrolls
- Auto-save

## Run (desktop)
```bash
pip install kivy
python main.py
```

## Build for Android
```bash
pip install buildozer
buildozer android debug
```

## Build for iOS
```bash
# Requires macOS with Xcode
pip install kivy-ios
toolchain build kivy
toolchain create Gladiator Idle .
```
