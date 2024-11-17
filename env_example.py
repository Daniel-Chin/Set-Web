from shared import *

# your monitor height in pixels
# lower this value if it takes too long to rasterize
TEXTURE_RESOLUTION = 2160

GLOBAL_SCALING = 1.6

FONT_SIZE = round(121 * GLOBAL_SCALING)

# card display width in pixels
CARD_WIDTH = round(100 * GLOBAL_SCALING)

# size multiplier for cards in the display cases
SMALL_CARD_RATIO = 0.4

# thickness indicator (width, height) in pixels
THICKNESS_INDICATOR_WEALTH = (
    round(70 * GLOBAL_SCALING), 
    round(70 * GLOBAL_SCALING), 
)
THICKNESS_INDICATOR_DECK = (
    round(140 * GLOBAL_SCALING), 
    round(140 * GLOBAL_SCALING), 
)

# padding in pixels
PADX = round(12 * GLOBAL_SCALING)
PADY = round(12 * GLOBAL_SCALING)

# Don't change the below. 
CARD_HEIGHT = round(CARD_WIDTH * CARD_ASPECT[1] / CARD_ASPECT[0])
