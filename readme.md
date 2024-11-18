# Set Web
Play the game Set over the internet.  

# How
## Client
- `pip install -r requirements.txt`
- `python client.py`
- For GUI options, edit ["./env.py"](./env.py)
  - If it's not existent, run "client.py" once. That will generate the default env.  

## Server
- `pip install -r requirements.txt`
- Get Cairo. 
  - On linux you probably already have it. 
  - On Windows you need GTK. 
  - On MacOS you can `brew install cairo`.  
- `python rasterize.py`
- `python server.py`

## Acknowledgement
- The card texture is taken from the wiki page. See  
  - https://en.wikipedia.org/wiki/Set_(card_game)
  - https://en.wikipedia.org/wiki/Set_(card_game)#/media/File:Set_isomorphic_cards.svg
