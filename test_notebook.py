
import tkinter as tk
from tkinter import ttk

root = tk.Tk()
root.title('Notebook Test')
root.geometry('600x400')
root.configure(bg='#1e1e1e')

style = ttk.Style()
style.theme_use('clam')
style.configure('TFrame', background='#1e1e1e')
style.configure('TNotebook', background='#1e1e1e', borderwidth=0)
style.configure('TNotebook.Tab', background='#2d2d2d', foreground='white', padding=[10, 2])
style.map('TNotebook.Tab', background=[('selected', '#007acc')], foreground=[('selected', 'white')])

main_frame = ttk.Frame(root, padding='15')
main_frame.pack(fill=tk.BOTH, expand=True)

notebook = ttk.Notebook(main_frame)
notebook.pack(fill=tk.BOTH, expand=True)

tab1 = ttk.Frame(notebook)
notebook.add(tab1, text='Positions')
lbl1 = ttk.Label(tab1, text='Tab 1 Content', background='#1e1e1e', foreground='white')
lbl1.pack(pady=20)

tab2 = ttk.Frame(notebook)
notebook.add(tab2, text='Order History')
tree = ttk.Treeview(tab2, columns=('A'), show='headings')
tree.heading('A', text='Order')
tree.insert('', tk.END, values=('Test Order',))
tree.pack(fill=tk.BOTH, expand=True)

root.after(3000, root.destroy)
root.mainloop()

