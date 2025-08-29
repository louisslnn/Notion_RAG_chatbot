import tkinter as tk

class RAGWindow(tk.Tk):
    def __init__(self, pipeline):
        super().__init__()
        self.pipeline = pipeline
        self.overrideredirect(True)  # no border
        self.geometry("400x300")
        self.configure(bg="white")

        self.input_box = tk.Entry(self, width=50)
        self.input_box.pack(pady=10)

        self.send_btn = tk.Button(self, text="Ask", command=self.ask)
        self.send_btn.pack()

        self.output_area = tk.Text(self, wrap="word", height=10)
        self.output_area.pack(pady=10)

        # draggable
        self.bind("<ButtonPress-1>", self.start_move)
        self.bind("<B1-Motion>", self.do_move)

    def start_move(self, event):
        self._x = event.x
        self._y = event.y

    def do_move(self, event):
        x = self.winfo_pointerx() - self._x
        y = self.winfo_pointery() - self._y
        self.geometry(f"+{x}+{y}")

    def ask(self):
        query = self.input_box.get()
        result = self.pipeline.ask_pipeline(query)
        self.output_area.delete(1.0, tk.END)
        self.output_area.insert(tk.END, result["answer"] if result.get("answer") else result.get("message"))

def run_app(pipeline):
    win = RAGWindow(pipeline)
    win.mainloop()
