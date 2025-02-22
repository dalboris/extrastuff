#This script authored by Rodney Baker and licensed CC-0.  For more information please see: <http://creativecommons.org/publicdomain/zero/1.0/>
#10/2/2024 Additional improvements to script suggesteed by Boris Dalstein (https://www.vgc.io/news)
#Please support his work on VGC Illustration which is leading to VGC Animation
import xml.etree.ElementTree as ET
import ast
import tkinter as tk
from tkinter import filedialog, messagebox
import os
import re
from io import BytesIO
from PIL import Image, ImageTk  # Requires Pillow library

try:
    import cairosvg  # Requires cairosvg library
except ImportError:
    cairosvg = None

def vgc_to_svg(vgc_content):
    """
    Converts VGCI content to SVG format without applying inputtransform to positions.
    """
    # Parse the XML content
    root = ET.fromstring(vgc_content)
    
    # Create the SVG root element
    svg = ET.Element('svg', xmlns="http://www.w3.org/2000/svg", version="1.1")
    
    # Initialize min and max values for viewBox calculation
    min_x = min_y = float('inf')
    max_x = max_y = float('-inf')
    
    # Collect all transformed positions for further processing
    all_edges = []
    
    for edge in root.findall('.//edge'):
        positions_str = edge.get('positions')
        widths_str = edge.get('widths')
        color_str = edge.get('color')
        inputtransform_str = edge.get('inputtransform')
        
        # Parse positions and widths
        try:
            positions = ast.literal_eval(positions_str)
            widths = ast.literal_eval(widths_str)
        except Exception as e:
            # Handle parsing errors
            print(f"Error parsing positions or widths: {e}")
            continue
        
        color = color_str  # Use the original color without inversion
        
        # NOTE: Do not apply inputtransform to positions
        # inputtransform is intended for inputpositions only
        
        # Use positions as-is
        transformed_positions = positions
        
        # Update min and max values based on positions
        xs = [x for x, y in transformed_positions]
        ys = [y for x, y in transformed_positions]
        
        min_x = min(min_x, min(xs))
        min_y = min(min_y, min(ys))
        max_x = max(max_x, max(xs))
        max_y = max(max_y, max(ys))
        
        # Store data for later
        all_edges.append({
            'positions': transformed_positions,
            'widths': widths,
            'color': color
        })
    
    # Compute total width and height for the viewBox
    total_width = max_x - min_x
    total_height = max_y - min_y
    
    if total_width == 0 or total_height == 0:
        # Prevent division by zero
        total_width = total_height = 1

    # Add a white background rectangle to the SVG
    background = ET.SubElement(svg, 'rect', {
        'width': str(total_width),
        'height': str(total_height),
        'fill': 'white'
    })

    # Now create path elements for each edge
    for edge_data in all_edges:
        transformed_positions = edge_data['positions']
        widths = edge_data['widths']
        color = edge_data['color']
        
        # Shift positions to start at (0,0)
        shifted_positions = [ (x - min_x, y - min_y) for x, y in transformed_positions ]
        
        # Create path data string
        if not shifted_positions:
            continue  # No positions to draw
        path_data = "M {} {}".format(*shifted_positions[0])
        for x, y in shifted_positions[1:]:
            path_data += " L {} {}".format(x, y)
        
        # Use the first width value or default to '1'
        stroke_width = str(widths[0]) if widths else '1'
        
        # Create the path element
        path = ET.SubElement(svg, 'path', {
            'd': path_data,
            'stroke': color,
            'fill': 'none',
            'stroke-width': stroke_width
        })
    
    # Set the viewBox attribute on the SVG element
    svg.set('viewBox', f'0 0 {total_width} {total_height}')
    
    # Convert the SVG element tree to a string
    svg_string = ET.tostring(svg, encoding='unicode')
    return svg_string

def svg_to_vgci(svg_content):
    """
    Converts SVG content to VGCI format, correctly handling open and closed paths.
    """
    # Parse the SVG content
    svg_root = ET.fromstring(svg_content)
    svg_ns = "http://www.w3.org/2000/svg"
    
    # Create the VGC root element
    vgc = ET.Element('vgc')
    
    # Variables for transformation (assuming viewBox starts at 0,0)
    viewBox = svg_root.get('viewBox')
    if viewBox:
        vb_values = [float(v) for v in viewBox.strip().split()]
        min_x, min_y, width, height = vb_values
    else:
        # If no viewBox, set defaults
        min_x = min_y = 0
        width = height = 0  # Will adjust based on content
    
    # Iterate over path elements
    for path_elem in svg_root.findall('.//{%s}path' % svg_ns):
        d_attr = path_elem.get('d')
        stroke_width = path_elem.get('stroke-width', '1')
        stroke_color = path_elem.get('stroke', 'rgb(0,0,0)')
        
        # Determine if the path is closed
        is_closed = False
        if re.search(r'[Zz]', d_attr):
            is_closed = True
        
        # Parse the path data (supports only 'M' and 'L' commands)
        # This regex will not capture 'Z' or 'z' commands
        commands = re.findall(r'([ML])\s*([-\d.]+)[,\s]+([-\d.]+)', d_attr)
        positions = []
        widths = []
        for cmd, x_str, y_str in commands:
            x = float(x_str) + min_x
            y = float(y_str) + min_y
            positions.append((x, y))
            widths.append(float(stroke_width))
        
        # If the path is closed, ensure the first and last positions are the same
        if is_closed:
            if positions and positions[0] != positions[-1]:
                positions.append(positions[0])
        
        # Create the edge element
        edge = ET.Element('edge', {
            'positions': str(positions),
            'widths': str(widths),
            'color': stroke_color,
            # Assuming no transformations
            'inputtransform': '((1, 0, 0), (0, 1, 0), (0, 0, 1))',
            'inputpenwidth': stroke_width,
            # Placeholder attributes
            'inputpositions': str(positions),
            'inputpressures': str([0.5] * len(positions)),
            'inputtimestamps': str([0] * len(positions)),
        })
        vgc.append(edge)
    
    # Convert the VGC element tree to a string
    vgci_string = ET.tostring(vgc, encoding='unicode')
    return vgci_string

class VGCtoSVGConverter:
    def __init__(self, root):
        self.root = root
        self.root.title("VGC2SVG - a VGC Illustration Converter")
        self.create_widgets()
        self.vgci_content = None
        self.svg_content = None
        self.output_content = None  # Holds either VGCI or SVG data
        self.file_path = None
        self.current_format = None  # 'vgci' or 'svg'
        self.image = None  # Keep a reference to the image to prevent garbage collection
        self.image_pil = None  # Holds PIL Image for exporting

    def create_widgets(self):
        # Create a menu bar
        menubar = tk.Menu(self.root)
        
        # Create a File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Open VGCI File", command=self.open_vgci_file)
        file_menu.add_command(label="Open SVG File", command=self.open_svg_file)
        file_menu.add_command(label="Save As VGCI...", command=self.save_vgci_file)
        file_menu.add_command(label="Save As SVG...", command=self.save_svg_file)
        file_menu.add_command(label="Export PNG Image...", command=self.export_png_image)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        
        menubar.add_cascade(label="File", menu=file_menu)
        
        # Set the menu bar
        self.root.config(menu=menubar)
        
        # Create a status label
        self.status_label = tk.Label(self.root, text="No file loaded.", anchor='w')
        self.status_label.pack(fill='x', padx=5, pady=5)
        
        # Create a frame for the image
        self.image_frame = tk.Frame(self.root)
        self.image_frame.pack(fill='both', expand=True)
        
        # Create a label to display the image
        self.image_label = tk.Label(self.image_frame)
        self.image_label.pack(fill='both', expand=True)

    def open_vgci_file(self):
        file_path = filedialog.askopenfilename(
            title="Select VGC Illustration File",
            filetypes=(("VGC Illustration Files", "*.vgci"), ("All Files", "*.*"))
        )
        if not file_path:
            return  # User cancelled
        
        # Read the content of the vgci file
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                self.vgci_content = f.read()
            self.file_path = file_path
            self.current_format = 'vgci'
            self.status_label.config(text=f"Loaded VGCI: {os.path.basename(file_path)}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to read the file:\n{e}")
            return
        
        # Convert the VGC content to SVG
        try:
            self.output_content = vgc_to_svg(self.vgci_content)
            messagebox.showinfo("Success", f"VGCI file converted to SVG.")
            self.display_svg_image(self.output_content)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to convert VGCI to SVG:\n{e}")
            self.output_content = None

    def open_svg_file(self):
        file_path = filedialog.askopenfilename(
            title="Select SVG File",
            filetypes=(("SVG Files", "*.svg"), ("All Files", "*.*"))
        )
        if not file_path:
            return  # User cancelled
        
        # Read the content of the SVG file
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                self.svg_content = f.read()
            self.file_path = file_path
            self.current_format = 'svg'
            self.status_label.config(text=f"Loaded SVG: {os.path.basename(file_path)}")
            # Display the SVG image
            self.display_svg_image(self.svg_content)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to read the file:\n{e}")
            return
        
        # Convert the SVG content to VGCI
        try:
            self.output_content = svg_to_vgci(self.svg_content)
            messagebox.showinfo("Success", f"SVG file converted to VGCI.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to convert SVG to VGCI:\n{e}")
            self.output_content = None

    def save_svg_file(self):
        if self.current_format != 'vgci' or not self.output_content:
            messagebox.showerror("Error", "No SVG data to save. Please open a VGCI file first.")
            return
        
        # Suggest a default file name
        if self.file_path:
            default_name = os.path.splitext(os.path.basename(self.file_path))[0] + '.svg'
        else:
            default_name = 'output.svg'
        
        save_path = filedialog.asksaveasfilename(
            title="Save SVG File",
            defaultextension=".svg",
            initialfile=default_name,
            filetypes=(("SVG Files", "*.svg"), ("All Files", "*.*"))
        )
        if not save_path:
            return  # User cancelled
        
        # Save the SVG output to a file
        try:
            with open(save_path, 'w', encoding='utf-8') as f:
                f.write(self.output_content)
            messagebox.showinfo("Success", f"SVG file saved to:\n{save_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save SVG file:\n{e}")

    def save_vgci_file(self):
        if self.current_format != 'svg' or not self.output_content:
            messagebox.showerror("Error", "No VGCI data to save. Please open an SVG file first.")
            return
        
        # Suggest a default file name
        if self.file_path:
            default_name = os.path.splitext(os.path.basename(self.file_path))[0] + '.vgci'
        else:
            default_name = 'output.vgci'
        
        save_path = filedialog.asksaveasfilename(
            title="Save VGCI File",
            defaultextension=".vgci",
            initialfile=default_name,
            filetypes=(("VGC Illustration Files", "*.vgci"), ("All Files", "*.*"))
        )
        if not save_path:
            return  # User cancelled
        
        # Save the VGCI output to a file
        try:
            with open(save_path, 'w', encoding='utf-8') as f:
                f.write(self.output_content)
            messagebox.showinfo("Success", f"VGCI file saved to:\n{save_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save VGCI file:\n{e}")

    def display_svg_image(self, svg_content):
        if cairosvg is None:
            messagebox.showerror("Error", "cairosvg is required to display SVG images. Please install it using 'pip install cairosvg'.")
            return
        
        try:
            # Convert SVG to PNG in memory, set background color to white
            png_data = cairosvg.svg2png(bytestring=svg_content.encode('utf-8'), background_color='white')
            # Load the image with PIL
            image = Image.open(BytesIO(png_data))
            # Store the PIL Image for exporting
            self.image_pil = image.copy()
            # Resize image to fit the label, if desired
            image.thumbnail((800, 600), Image.LANCZOS)
            # Convert to PhotoImage
            self.image = ImageTk.PhotoImage(image)
            # Display the image
            self.image_label.config(image=self.image)
            self.image_label.image = self.image  # Keep a reference
        except Exception as e:
            messagebox.showerror("Error", f"Failed to display SVG image:\n{e}")

    def export_png_image(self):
        if self.image_pil is None:
            messagebox.showerror("Error", "No PNG image to export. Please open and convert a VGCI or SVG file first.")
            return

        # Suggest a default file name
        if self.file_path:
            default_name = os.path.splitext(os.path.basename(self.file_path))[0] + '.png'
        else:
            default_name = 'output.png'

        save_path = filedialog.asksaveasfilename(
            title="Export PNG Image",
            defaultextension=".png",
            initialfile=default_name,
            filetypes=(("PNG Files", "*.png"), ("All Files", "*.*"))
        )
        if not save_path:
            return  # User cancelled

        # Save the PIL image to a file
        try:
            self.image_pil.save(save_path)
            messagebox.showinfo("Success", f"PNG image exported to:\n{save_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export PNG image:\n{e}")

if __name__ == "__main__":
    root = tk.Tk()
    app = VGCtoSVGConverter(root)
    root.mainloop()
