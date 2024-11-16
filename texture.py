'''
[c, f, n, s], i.e., [color, fill, number, shape]
'''
import random

import cairosvg
from PIL import Image, ImageTk
import tkinter as tk

CARD_ASPECT = (43, 62)
SCALE = round(2160 / 3 / CARD_ASPECT[1])
CARD_RESOLUTION = (CARD_ASPECT[0] * SCALE, CARD_ASPECT[1] * SCALE)

SVG = './texture.svg'
PNG = './cache/texture.png'

def bboxOf(x: int, y: int):
    return (x * CARD_RESOLUTION[0], y * CARD_RESOLUTION[1], (x + 1) * CARD_RESOLUTION[0], (y + 1) * CARD_RESOLUTION[1])

class Texture:
    def __init__(self, tkRoot: tk.Tk):
        _ = tkRoot  # Just lexical message, because root is required by ImageTk.PhotoImage.
        print('Rasterizing texture... ', end='', flush=True)
        cairosvg.svg2png(
            url=SVG, write_to=PNG, 
            output_width =CARD_RESOLUTION[0] * 9, 
            output_height=CARD_RESOLUTION[1] * 9, 
            dpi=1,  # small dpi fixes repeated <pattern> interpolation
        )
        print('ok')

        family_photo = Image.open(PNG)

        self.photoImgs = []
        for c in range(3):
            C = []
            self.photoImgs.append(C)
            for f in range(3):
                F = []
                C.append(F)
                for n in range(3):
                    N = []
                    F.append(N)
                    for s in range(3):
                        cropped = family_photo.crop(bboxOf(
                            c * 3 + f, n * 3 + s, 
                        ))
                        N.append(ImageTk.PhotoImage(cropped))
    
    def get(self, c: int, f: int, n: int, s: int):
        return self.photoImgs[c][f][n][s]

def test():
    root = tk.Tk()
    root.title("Textures")
    texture = Texture(root)

    refs = []
    for _ in range(4):
        c = random.randint(0, 2)
        f = random.randint(0, 2)
        n = random.randint(0, 2)
        s = random.randint(0, 2)
        label = tk.Label(root, text=f'[{c=}, {f=}, {n=}, {s=}]')
        label.pack(side=tk.LEFT)
        img = texture.get(c, f, n, s)
        # img = ImageTk.PhotoImage(texture.family_photo.crop(bboxOf(0,0)))
        label = tk.Label(root, image=img)
        label.keep_ref_to_img = img
        refs.append(label)
        label.pack(side=tk.LEFT)

    root.mainloop()

if __name__ == "__main__":
    test()
