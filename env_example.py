from shared import *

# your monitor height in pixels
# lower this value if it takes too long to rasterize
TEXTURE_RESOLUTION = 2160

# card display width in pixels
CARD_WIDTH = 200
SMALL_CARD_WIDTH = 100

# padding in pixels
PADX = 16
PADY = 16

# Don't change the below. 
CARD_HEIGHT       = round(CARD_WIDTH       * CARD_ASPECT[1] / CARD_ASPECT[0])
SMALL_CARD_HEIGHT = round(SMALL_CARD_WIDTH * CARD_ASPECT[1] / CARD_ASPECT[0])
