#!/usr/bin/env python3
import sys
from tkinter import Tk, Label

title = sys.argv[1] if len(sys.argv) > 1 else "Settings (dummy)"

root = Tk()
root.title(title)
root.geometry("800x480")
root.configure(bg="#000000")

Label(
    root,
    text=title,
    font=("Arial", 20, "bold"),
    bg="#000000",
    fg="#1E6BFF"
).pack(pady=30)

Label(
    root,
    text="Pantalla dummy. Reemplazar por configurador real cuando esté.",
    font=("Arial", 14),
    bg="#000000",
    fg="white"
).pack(pady=10)

root.mainloop()
