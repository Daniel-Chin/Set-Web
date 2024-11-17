'''
[c, f, n, s], i.e., [color, fill, number, shape]
'''
import random

import cairosvg
from PIL import Image, ImageTk
import tkinter as tk

from shared import *
from env_wrap import *

SCALE = round(TEXTURE_RESOLUTION / 3 / CARD_ASPECT[1])
CARD_RESOLUTION = (CARD_ASPECT[0] * SCALE, CARD_ASPECT[1] * SCALE)

SVG = './texture.svg'
PNG = './cache/texture.png'

def bboxOf(x: int, y: int):
    return (x * CARD_RESOLUTION[0], y * CARD_RESOLUTION[1], (x + 1) * CARD_RESOLUTION[0], (y + 1) * CARD_RESOLUTION[1])

class Texture:
    def __init__(self, tkRoot: tk.Tk):
        _ = tkRoot  # Just lexical message, because root is required by ImageTk.PhotoImage.
        print('Rasterizing texture...')
        cairosvg.svg2png(
            url=SVG, write_to=PNG, 
            output_width =CARD_RESOLUTION[0] * 9, 
            output_height=CARD_RESOLUTION[1] * 9, 
            dpi=1,  # small dpi fixes repeated <pattern> interpolation
        )
        print('ok')

        family_photo = Image.open(PNG)

        self.photoImgs: tp.Dict[tp.Tuple[
            int, int, int, int, 
        ], ImageTk.PhotoImage] = {}
        for c, f, n, s in iterAllCards():
            cropped = family_photo.crop(bboxOf(
                c * 3 + f, n * 3 + s, 
            ))
            de_bordered = cropped.crop((
                round(CARD_RESOLUTION[0] * 0.1),
                round(CARD_RESOLUTION[1] * 0.1),
                round(CARD_RESOLUTION[0] * 0.9),
                round(CARD_RESOLUTION[1] * 0.9),
            ))
            resized = de_bordered.resize((CARD_WIDTH, CARD_HEIGHT))
            self.photoImgs[(c, f, n, s)] = ImageTk.PhotoImage(resized)
    
    def get(self, c: int, f: int, n: int, s: int):
        return self.photoImgs[(c, f, n, s)]

def test():
    root = tk.Tk()
    root.title("Textures")
    texture = Texture(root)

    for _ in range(4):
        c = random.randint(0, 2)
        f = random.randint(0, 2)
        n = random.randint(0, 2)
        s = random.randint(0, 2)
        label = tk.Label(root, text=f'[{c=}, {f=}, {n=}, {s=}]')
        label.pack(side=tk.LEFT)
        img = texture.get(c, f, n, s)
        label = tk.Label(root, image=img)   # type: ignore
        label.pack(side=tk.LEFT)

    root.mainloop()

if __name__ == "__main__":
    test()
