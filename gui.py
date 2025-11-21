import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import sys
import threading
import queue
import os
import subprocess
import shutil
try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except Exception:
    PIL_AVAILABLE = False

# Prefer the new CLI entrypoint (main.py). Fall back to calling process_image
# directly if main isn't importable.
cli_entry = None
cli_main = None
cli_process_image = None
try:
    from main import main as cli_main
    cli_entry = "main"
except Exception:
    try:
        from process_image import process_image as cli_process_image
        cli_entry = "process_image"
    except Exception:
        print("Error: Please place this script in the root directory, next to process_image.py or main.py")
        sys.exit(1)

class ConsoleRedirector:
    """Redirects stdout to a Tkinter Text widget."""
    def __init__(self, text_widget, tag="stdout"):
        self.text_widget = text_widget
        self.tag = tag
        self.queue = queue.Queue()

    def write(self, str_val):
        self.queue.put(str_val)

    def flush(self):
        pass

class ParcVisApp(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("ParcVis GUI")
        self.geometry("700x750")

        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        style = ttk.Style()
        style.theme_use("clam")

        self.create_file_inputs()
        self.create_options()
        self.create_console()
        self.create_actions()

        self.after(100, self.check_queue)

    def create_file_inputs(self):
        frame = ttk.LabelFrame(self, text="Input / Output", padding=10)
        frame.grid(row=0, column=0, sticky="ew", padx=10, pady=5)
        frame.columnconfigure(1, weight=1)
        ttk.Label(frame, text="NIfTI Map (Required):").grid(row=0, column=0, sticky="w")
        self.nifti_path = tk.StringVar()
        ttk.Entry(frame, textvariable=self.nifti_path).grid(row=0, column=1, sticky="ew", padx=5)
        ttk.Button(frame, text="Browse", command=lambda: self.browse_file(self.nifti_path)).grid(row=0, column=2)

        ttk.Label(frame, text="Anatomical (Optional):").grid(row=1, column=0, sticky="w", pady=5)
        self.anat_path = tk.StringVar()
        ttk.Entry(frame, textvariable=self.anat_path).grid(row=1, column=1, sticky="ew", padx=5, pady=5)
        ttk.Button(frame, text="Browse", command=lambda: self.browse_file(self.anat_path)).grid(row=1, column=2, pady=5)

        ttk.Label(frame, text="Output Name:").grid(row=2, column=0, sticky="w")
        self.output_name = tk.StringVar(value="parcvis_output")
        ttk.Entry(frame, textvariable=self.output_name).grid(row=2, column=1, sticky="ew", padx=5)

    def create_options(self):
        frame = ttk.LabelFrame(self, text="Configuration", padding=10)
        frame.grid(row=1, column=0, sticky="ew", padx=10, pady=5)
        
        
        ttk.Label(frame, text="Sign:").grid(row=0, column=0, sticky="w")
        self.sign_var = tk.StringVar(value="both")
        ttk.Combobox(frame, textvariable=self.sign_var, values=["pos", "neg", "both"], state="readonly", width=10).grid(row=0, column=1, sticky="w", padx=5)

        ttk.Label(frame, text="Threshold:").grid(row=0, column=2, sticky="w", padx=10)
        self.thr_var = tk.DoubleVar(value=0.2)
        ttk.Entry(frame, textvariable=self.thr_var, width=10).grid(row=0, column=3, sticky="w")

        ttk.Label(frame, text="DPI:").grid(row=0, column=4, sticky="w", padx=10)
        self.dpi_var = tk.IntVar(value=150)
        ttk.Entry(frame, textvariable=self.dpi_var, width=8).grid(row=0, column=5, sticky="w")

        
        ttk.Label(frame, text="Annotation:").grid(row=1, column=0, sticky="w", pady=10)
        self.annot_var = tk.StringVar(value="minimal")
        ttk.Combobox(frame, textvariable=self.annot_var, values=["none", "minimal", "full"], state="readonly", width=10).grid(row=1, column=1, sticky="w", padx=5, pady=10)

        ttk.Label(frame, text="Components (e.g. 1 4 2):").grid(row=1, column=2, sticky="w", padx=10)
        self.comps_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.comps_var).grid(row=1, column=3, columnspan=3, sticky="ew")

        
        self.rich_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(frame, text="Rich Output (JSON/CSV)", variable=self.rich_var).grid(row=2, column=0, columnspan=2, sticky="w")

        self.norm_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(frame, text="Normalize Data", variable=self.norm_var).grid(row=2, column=2, columnspan=2, sticky="w")

        self.extend_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(frame, text="Extended View (QC)", variable=self.extend_var).grid(row=2, column=4, columnspan=2, sticky="w")

    def create_console(self):
        frame = ttk.LabelFrame(self, text="Log / Progress", padding=10)
        frame.grid(row=2, column=0, sticky="nsew", padx=10, pady=5)
        
        self.console_text = tk.Text(frame, height=8, state="disabled", bg="#1e1e1e", fg="#00ff00", font=("Consolas", 10))
        self.console_text.pack(fill="both", expand=True)

        self.redirector = ConsoleRedirector(self.console_text)
        sys.stdout = self.redirector
        sys.stderr = self.redirector

        self.create_image_panel()

    def create_actions(self):
        frame = ttk.Frame(self, padding=10)
        frame.grid(row=3, column=0, sticky="ew")

        self.run_button = ttk.Button(frame, text="Run ParcVis", command=self.start_thread)
        self.run_button.pack(side="right", padx=5)
        ttk.Button(frame, text="Exit", command=self.destroy).pack(side="right")

    def create_image_panel(self):
        """Create a frame to display the generated image preview."""
        frame = ttk.LabelFrame(self, text="Preview", padding=6)
        frame.grid(row=4, column=0, sticky="nsew", padx=10, pady=5)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)

        self.preview_label = ttk.Label(frame)
        self.preview_label.grid(row=0, column=0, sticky="nsew")
        self.preview_image = None
        self.open_button = ttk.Button(frame, text="Open PNG", command=self.open_image_external)
        self.open_button.grid(row=1, column=0, sticky="e", pady=(6, 0))
        self.open_button.config(state="disabled")
        self.last_png_path = None

    def browse_file(self, var):
        filename = filedialog.askopenfilename(filetypes=[("NIfTI files", "*.nii *.nii.gz"), ("All files", "*.*")])
        if filename:
            var.set(filename)

    def check_queue(self):
        """Polls the queue for new output from the thread."""
        try:
            while True:
                msg = self.redirector.queue.get_nowait()
                self.console_text.config(state="normal")
                self.console_text.insert("end", msg)
                self.console_text.see("end")
                self.console_text.config(state="disabled")
        except queue.Empty:
            pass
        finally:
            self.after(100, self.check_queue)

    def start_thread(self):
        
        try:
            self.run_button.config(state="disabled")
        except Exception:
            pass
        threading.Thread(target=self.run_process, daemon=True).start()

    def run_process(self):
        
        nifti = self.nifti_path.get()
        if not nifti:
            messagebox.showerror("Error", "Please select a NIfTI map file.")
            return

        anat = self.anat_path.get() if self.anat_path.get() else None
        
        
        raw_comps = self.comps_var.get().strip()
        components = None
        if raw_comps:
            try:
                components = [int(x) for x in raw_comps.replace(",", " ").split()]
            except ValueError:
                print("Error: Components must be a list of numbers.")
                return

        
        print("--- Starting ParcVis ---")
        try:
            if cli_entry == "main" and cli_main is not None:
                argv = []
                argv += ["-n", nifti]
                if anat:
                    argv += ["-a", anat]
                argv += ["-s", self.sign_var.get()]
                if self.output_name.get():
                    argv += ["-o", self.output_name.get()]
                if self.rich_var.get():
                    argv += ["--rich"]
                if not self.norm_var.get():
                    argv += ["--no-norm"]
                if self.extend_var.get():
                    argv += ["--extend"]
                argv += ["--thr", str(self.thr_var.get())]
                argv += ["--dpi", str(self.dpi_var.get())]
                argv += ["--annotate", self.annot_var.get()]
                if components is not None:
                    argv += ["-c"] + [str(x) for x in components]

                cli_main(argv)
                savedir, filename, ext = __import__("src.utils", fromlist=["process_output_path"]).process_output_path(self.output_name.get())
                png_path = os.path.join(savedir, f"{filename}.png") if "png" in ext else os.path.join(savedir, f"{filename}.{ext[0]}")
            elif cli_entry == "process_image" and cli_process_image is not None:
                cli_process_image(
                    NIFTI=nifti,
                    ANAT=anat,
                    SGN=self.sign_var.get(),
                    output=self.output_name.get(),
                    rich=self.rich_var.get(),
                    thr=self.thr_var.get(),
                    normalize=self.norm_var.get(),
                    extend=self.extend_var.get(),
                    dpi=self.dpi_var.get(),
                    annotate=self.annot_var.get(),
                    components=components,
                    cut=None,
                )
            else:
                raise RuntimeError("No CLI entrypoint available to run ParcVis")

            
            try:
                self.after(0, lambda p=png_path: self.on_process_success(p))
            except Exception:
                self.after(0, lambda: self.on_process_success(None))
        except Exception as e:
            print(f"\nCRITICAL ERROR: {str(e)}")
            messagebox.showerror("Error", f"An error occurred:\n{str(e)}")

    def on_process_success(self, png_path):
        """Called in the main thread when processing finishes successfully."""
        messagebox.showinfo("Success", "Processing Complete!")
        try:
            if png_path and os.path.exists(png_path):
                self.last_png_path = png_path
                # enable external opener
                try:
                    self.open_button.config(state="normal")
                except Exception:
                    pass
                if PIL_AVAILABLE:
                    self.display_image(png_path)
                else:
                    print("Pillow not available: cannot show preview. PNG saved at:", png_path)
        finally:
            try:
                self.run_button.config(state="normal")
            except Exception:
                pass

    def open_image_external(self, path=None):
        """Open `path` (or last generated PNG) in the system default image viewer."""
        p = path or self.last_png_path
        if not p or not os.path.exists(p):
            messagebox.showerror("Error", "No PNG available to open")
            return
        try:
            if sys.platform.startswith("win"):
                os.startfile(p)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", p])
            else:
                # Linux/Unix: prefer xdg-open, fall back to gio
                opener = shutil.which("xdg-open") or shutil.which("gio") or shutil.which("xdg")
                if opener:
                    subprocess.Popen([opener, p])
                else:
                    # As a fallback, try `display` (ImageMagick)
                    magick = shutil.which("display")
                    if magick:
                        subprocess.Popen([magick, p])
                    else:
                        messagebox.showerror("Error", "No known image opener found (install xdg-open or ImageMagick)")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open image: {e}")

    def display_image(self, path):
        """Load an image from `path` and display it in the preview label, resizing to fit."""
        try:
            img = Image.open(path)
            # compute available space (preview_label size)
            max_w = max(200, self.preview_label.winfo_width() or 400)
            max_h = max(200, self.preview_label.winfo_height() or 300)
            img.thumbnail((max_w, max_h), Image.LANCZOS)
            photo = ImageTk.PhotoImage(img)
            self.preview_label.config(image=photo)
            # keep a reference to avoid GC
            self.preview_image = photo
        except Exception as e:
            print("Failed to display image preview:", e)

if __name__ == "__main__":
    app = ParcVisApp()
    app.mainloop()