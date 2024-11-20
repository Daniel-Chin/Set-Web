# Set Web
Play the game Set over the internet.  

## How
You need python >= 3.8.  

### Client
- `pip install -r requirements.txt`
- `python client.py`
- For GUI options, edit ["./env.py"](./env.py)
  - If it's not existent, run "client.py" once. That will generate the default env.  

### Server
- `pip install -r requirements.txt`
- Get Cairo. 
  - On linux you probably already have it. 
  - On Windows you need GTK. 
  - On MacOS you can `brew install cairo`.  
    - Special thanks: Wenye Ma.  
- `python rasterize.py`
- `python server.py`

## Troubleshoot
### Linux freezes
- Behavior: entire Linux OS freezes in the game.  
- Solution: (Believe it or not,) use `uv` instead of `conda` to install the environment.  
- Cause: GPU HANG (try `journalctl -b 1 | grep GPU` after you reboot from the freeze)
- Tested on KDE Plasma Wayland/X11.  
- Special thanks: Lejun Min

## Acknowledgement
- The card texture is taken from the wiki page. See  
  - https://en.wikipedia.org/wiki/Set_(card_game)
  - https://en.wikipedia.org/wiki/Set_(card_game)#/media/File:Set_isomorphic_cards.svg

## Other special thanks
- Provided valuable feature requests, suggestions, and testing:  
  - Liwei Lin; 2jjy; Wenye Ma;  
