'''
[c, f, n, s], i.e., [color, fill, number, shape]
'''
import random

from PIL import Image, ImageTk
import tkinter as tk

from shared import *
from env_wrap import *

def bboxOf(x: int, y: int):
    return (x * CARD_TEXTURE_RESOLUTION[0], y * CARD_TEXTURE_RESOLUTION[1], (x + 1) * CARD_TEXTURE_RESOLUTION[0], (y + 1) * CARD_TEXTURE_RESOLUTION[1])

class Texture:
    def __init__(self, tkRoot: tk.Tk):
        _ = tkRoot  # Just lexical message, because root is required by ImageTk.PhotoImage.

        family_photo = Image.open(PNG)

        self.photoImgs: tp.Dict[tp.Tuple[
            int, int, int, int, bool, 
        ], ImageTk.PhotoImage] = {}
        self.just_trying_to_have_a_reference = []
        for c, f, n, s in iterAllCards():
            cropped = family_photo.crop(bboxOf(
                c * 3 + f, n * 3 + s, 
            ))
            de_bordered = cropped.crop((
                round(CARD_TEXTURE_RESOLUTION[0] * 0.1),
                round(CARD_TEXTURE_RESOLUTION[1] * 0.1),
                round(CARD_TEXTURE_RESOLUTION[0] * 0.9),
                round(CARD_TEXTURE_RESOLUTION[1] * 0.9),
            ))
            resized = de_bordered.resize((CARD_WIDTH, CARD_HEIGHT))
            self.just_trying_to_have_a_reference.append(resized)
            self.photoImgs[(c, f, n, s, False)] = ImageTk.PhotoImage(resized)
            small = resized.resize((
                round(SMALL_CARD_RATIO * CARD_WIDTH),
                round(SMALL_CARD_RATIO * CARD_HEIGHT),
            ))
            self.just_trying_to_have_a_reference.append(small)
            self.photoImgs[(c, f, n, s, True)] = ImageTk.PhotoImage(small)
    
    def get(self, c: int, f: int, n: int, s: int, is_small: bool):
        return self.photoImgs[(c, f, n, s, is_small)]

def test():
    root = tk.Tk()
    root.title("Textures")
    texture = Texture(root)

    for _ in range(4):
        c = random.randint(0, 2)
        f = random.randint(0, 2)
        n = random.randint(0, 2)
        s = random.randint(0, 2)
        is_small = random.choice([True, False])
        label = tk.Label(root, text=f'[{c=}, {f=}, {n=}, {s=}]')
        label.pack(side=tk.LEFT)
        img = texture.get(c, f, n, s, is_small)
        label = tk.Label(root, image=img)   # type: ignore
        label.pack(side=tk.LEFT)

    root.mainloop()

if __name__ == "__main__":
    test()
