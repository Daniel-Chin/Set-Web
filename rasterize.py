import cairosvg

from shared import *
from env_wrap import *

def main():
    print('Rasterizing texture...')
    cairosvg.svg2png(
        url=SVG, write_to=PNG, 
        output_width =CARD_TEXTURE_RESOLUTION[0] * 9, 
        output_height=CARD_TEXTURE_RESOLUTION[1] * 9, 
        dpi=1,  # small dpi fixes repeated <pattern> interpolation
    )
    print('ok')

if __name__ == "__main__":
    main()
