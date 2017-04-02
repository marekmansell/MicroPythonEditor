import tkinter as tk
from tkinter import ttk
import serial # requires installing
import serial.tools.list_ports
from time import sleep, time
import threading 
from PIL import Image, ImageTk # requires installing
import logging
import queue
import os
import subprocess
from tkinter import filedialog
import sys

# tkinter on scrollbar instead of loo 60ms!!!
# every single fucking tab!!!!

logging.basicConfig(level=logging.DEBUG,
                    format='(%(threadName)-10s) %(message)s',
                    )

class NotebookTab(ttk.Frame):
    def __init__(self, master, title, file):
        super().__init__(master)
        self.master = master   
        self.title = title
        self.file = file

        self.text_area = tk.Text(self)
        self.text_area.grid(row=0, column=1)

        self.y_scrollbar = tk.Scrollbar(self)
        self.y_scrollbar.config(command=self.text_area.yview)
        self.y_scrollbar.grid(row=0, column=2, sticky=tk.N+tk.S)
        self.x_scrollbar = tk.Scrollbar(self)
        self.x_scrollbar.config(command=self.text_area.xview, orient=tk.HORIZONTAL)
        self.x_scrollbar.grid(row=1, column=1, sticky=tk.E+tk.W)

        self.line_numbers = tk.Canvas(self, width=28)
        self.line_numbers.grid(row=0, column=0, sticky=tk.N+tk.S)

        self.text_area.config(
            # bg="black",  # background color
            # fg="green",  # default text color
            wrap=tk.NONE,  # allows lines to be infinitely long
            yscrollcommand=self.y_scrollbar.set,
            xscrollcommand=self.x_scrollbar.set,
            font="{fixedsys} 12",
            # insertbackground="white",  # cursor color
        )

        self.last_line_number = None
        self.update_line_numbers()

        self.text_area.bind("<Tab>", self._tab_event)
        # self.text_area.bind("<Shift-ISO_Left_Tab>", self._shift_tab_event)
        self.text_area.bind("<Control-a>", self._control_a_event)
        self.text_area.bind("<Control-A>", self._control_a_event)
        self.text_area.bind("<Key>", self._key_event)

        if file:
            with open(file, "r") as f:
                file_content = f.read()
            self.text_area.insert("1.0", file_content)

    def _key_event(self, event):
        if self.text_area.edit_modified():
            self.master.tab(self.master.select(), text=self.title+" *")

    def _tab_event(self, event):
        self.text_area.insert(tk.INSERT, " " * 4)
        self._key_event(event)
        return 'break'

    def _shift_tab_event(self, event):
        return 'break'

    def _control_a_event(self, event):
        self.text_area.tag_add("sel", "1.0", "end")
        return 'break'

    def update_line_numbers(self):
        line = self.text_area.index('@0,0')
        if (self.last_line_number != line) or (self.last_line_number is None):
            self.line_numbers.delete("all")

            while True:
                dline = self.text_area.dlineinfo(line)
                if dline is None:
                    break
                y = dline[1]
                linenum = str(line).split(".")[0]
                self.line_numbers.create_text(2, y, anchor="nw", text=linenum)
                line = self.text_area.index("%s+1line" % line)

            self.last_line_number = line

    def save_file(self):
        if self.file and os.path.exists(self.file):
            with open(self.file, "w") as f:
                f.write(self.text_area.get(1.0, tk.END)[:-1]) # Text.get adds \n to the end, so this must be cut with [:-1]
            self.master.tab(self.master.select(), text=self.title)
        else:
            self.file = filedialog.asksaveasfilename(initialdir = "",title = "Save File",filetypes = (("python files","*.py"),("all files","*.*")))
            with open(self.file, "w") as f:
                f.write(self.text_area.get(1.0, tk.END))
            self.title = os.path.basename(self.file)
            self.master.tab(self.master.select(), text=self.title)


class SerialSetupWindow(tk.Toplevel):
    def __init__(self, master, command):
        super().__init__(master)
        self.title("Connect to MicroPython serial device")
        self.attributes("-topmost", True)
        self.grab_set()
        self.command = command

        if sys.platform == "linux":
            self.usb_devices = self._get_usb_devices_linux()

        if sys.platform == "win32":
            ports = list(serial.tools.list_ports.comports())
            self.usb_devices = [dev.device for dev in ports]

        
        buttons = []
        for i, device in enumerate(self.usb_devices):
            buttons.append(tk.Button(self, text=device, command=lambda dev=device: self.button_pressed(dev)))
            buttons[-1].grid()

    def _get_usb_devices_linux(self):
        serial_devices = subprocess.check_output("ls /dev/serial/by-path/; exit 0", stderr=subprocess.STDOUT, shell=True)
        serial_devices = serial_devices.decode().strip().split("\n")
        serial_devices = [x.strip() for x in serial_devices]
        serial_devices = [os.path.realpath(os.path.join("/dev/serial/by-path/", x)) for x in serial_devices]
        return serial_devices

    def button_pressed(self, device):
        self.command(device)
        self.grab_release() # to return to normal
        self.destroy()


class Editor(tk.Frame):
    def __init__(self, master):
        super().__init__(master)
        self.master = master
        self.grid_columnconfigure(0, weight=1)

        self.notebook_tabs = []
        self.notebook = ttk.Notebook(self)
        self.notebook.grid(row=0)
        self.new_tab()

        self.line_number_update_timer()

        self.repl_visible = False
        
        self.setup_device()

    def setup_device(self):
        SerialSetupWindow(self, self.connect)

    def connect(self, device):
        self.master.change_title(device)
        self.u_serial = uSerial(device)
        self.repl = Repl(self, self.u_serial)

    def line_number_update_timer(self):
        self.selected_tab_object().update_line_numbers()
        self.master.after(60, self.line_number_update_timer)

    def _add_tab(self, title, file):
        new_tab = NotebookTab(self.notebook, title, file)
        self.notebook_tabs.append(new_tab)
        self.notebook.add(new_tab, text=title)
        self.notebook.select(new_tab)

    def selected_tab_index(self):
        return self.notebook.index(self.notebook.select())

    def selected_tab_object(self):
        return self.notebook_tabs[self.selected_tab_index()]

    def run_tab(self):
        self.set_repl_visible()
        self.u_serial.run(self.selected_tab_object().text_area.get(1.0, tk.END).encode())

    def new_tab(self, title="untitled", file=None):
        if len(self.notebook_tabs) < 10:
            self._add_tab(title, file)

    def toggle_repl(self):
        if self.repl_visible:
            self.set_repl_invisible()
        else:
            self.set_repl_visible()

    def set_repl_visible(self):
        self.repl_visible = True
        self.repl.grid(row=1, sticky=tk.W+tk.E)

    def set_repl_invisible(self):
        self.repl_visible = False
        self.repl.grid_remove()

    def save_file(self):
        self.selected_tab_object().save_file()

    def load_file(self):
        file_path = filedialog.askopenfilename(initialdir = "",title = "Load file",filetypes = (("python files","*.py"),("all files","*.*")))
        if os.path.exists(file_path):
            self.new_tab(file=file_path, title=os.path.basename(file_path))


class FileManager(tk.Frame):
    def __init__(self, master, u_serial):
        super().__init__(master)
        self.grid_columnconfigure(0, weight=1)
        self.t = tk.Text(self)
        self.t.grid(row=0, sticky=tk.W+tk.E+tk.S+tk.N)


class Repl(tk.Frame):
    def __init__(self, master, u_serial):
        super().__init__(master)
        self.grid_columnconfigure(0, weight=1)
        self.repl_text_field = tk.Text(self)
        self.repl_text_field.grid(row=0, column=0, sticky=tk.W+tk.E)
        self.repl_scrollbar = tk.Scrollbar(self)
        self.repl_scrollbar.grid(row=0, column=1, sticky=tk.N+tk.S)
        self.repl_scrollbar.config(command=self.repl_text_field.yview)
        self.repl_stop = self.repl_text_field.index("end")
        self.send_queue = queue.Queue()

        self.repl_text_field.config(
            height=15,
            yscrollcommand=self.repl_scrollbar.set,
            # background="black",
            # foreground="yellow",
            # insertbackground="white",  # cursor color
        )


        self.repl_text_field.bind("<Key>", self._key_event)
        self.repl_text_field.bind("<Control-a>", self._ctrl_a_event)
        self.repl_text_field.bind("<Control-A>", self._ctrl_a_event)
        self.repl_text_field.bind("<Control-b>", self._ctrl_b_event)
        self.repl_text_field.bind("<Control-B>", self._ctrl_b_event)
        self.repl_text_field.bind("<Control-c>", self._ctrl_c_event)
        self.repl_text_field.bind("<Control-C>", self._ctrl_c_event)
        self.repl_text_field.bind("<Control-d>", self._ctrl_d_event)
        self.repl_text_field.bind("<Control-D>", self._ctrl_d_event)
        self.repl_text_field.bind("<Control-e>", self._ctrl_e_event)
        self.repl_text_field.bind("<Control-E>", self._ctrl_e_event)

        self.serial_thread = SerialThread(self, u_serial)

    def _key_event(self, event):
        if event.keysym == "Left" and self.repl_text_field.compare(self.repl_text_field.index(tk.INSERT), '==', self.repl_stop):
            return "break"
        if event.keysym == "BackSpace" and self.repl_text_field.compare(self.repl_text_field.index(tk.INSERT), '==', self.repl_stop):
            return "break"
        if event.keysym == "Up":
            return "break"
        if self.repl_text_field.compare(self.repl_text_field.index(tk.INSERT), '<', self.repl_stop):
            self.repl_text_field.mark_set("insert", self.repl_stop)
            return "break"
        if event.keysym == "Tab":
            self.repl_text_field.insert(tk.INSERT, " " * 4)
            return 'break'
        if event.keysym == "Return":
            to_send = self.repl_text_field.get(self.repl_stop, tk.END).rstrip()
            to_send += "\r"
            to_send = to_send.encode()
            self.repl_text_field.delete(self.repl_stop, tk.END)
            self.send_queue.put(to_send)
            return "break" 

    def _ctrl_a_event(self, event):
        self.send_queue.put(chr(1).encode())
        return "break"

    def _ctrl_b_event(self, event):
        self.send_queue.put(chr(2).encode())
        return "break"

    def _ctrl_c_event(self, event):
        self.send_queue.put(chr(3).encode())
        return "break"

    def _ctrl_d_event(self, event):
        self.send_queue.put(chr(4).encode())
        return "break"

    def _ctrl_e_event(self, event):
        self.send_queue.put(chr(5).encode())
        return "break"


class Toolbar(tk.Frame):
    def __init__(self, master):
        super().__init__(master, borderwidth=2)

        self.images = []
        self.buttons = {}

        self._add_button("new", "img/new.png")
        self._add_button("load_file", "img/load_file.png")
        self._add_button("save_file", "img/save.png")
        self._add_separator("separator_1")
        self._add_separator("separator_2")
        self._add_button("run", "img/run.png")
        self._add_button("repl", "img/repl.png")
        self._add_button("files", "img/files.png")
        self._add_button("device", "img/device.png")


    def _load_image(self, img_file):
        # Load the image first as PNGs and use ImageTk to convert
        # them to usable Tkinter image.
        img = Image.open(img_file)
        img = img.resize((40, 40), Image.ANTIALIAS)
        img = ImageTk.PhotoImage(img)
        
        # The image must be stored somewhere forever
        self.images.append(img)
        return self.images[-1]

    def _add_button(self, name, img_file):
        new_button = tk.Button(self, image=self._load_image(img_file))
        new_button.grid(row=0, column=len(self.buttons))
        self.buttons[name] = new_button

    def _add_separator(self, name):
        new_separator = ttk.Separator(self,orient=tk.VERTICAL)
        new_separator.grid(row=0, column=len(self.buttons), sticky=tk.N+tk.S)
        self.buttons[name] = new_separator


class uSerial:
    def __init__(self, port):
        self.serial = serial.Serial(port, baudrate=115200, timeout=.2)
        self.serial.flushInput()

    def read(self, num):
        return self.serial.read(num)
        
    def inWaiting(self):
        return self.serial.inWaiting()

    def write(self,msg):
        self.serial.write(msg)

    def is_open(self):
        return self.serial.is_open

    def close(self):
        self.serial.close()

    def run(self, command):
        self.enter_raw_repl()
        self.exec(command)
        self.exit_raw_repl()

    def run_file(self, filename):
        with open(filename, 'rb') as f:
            pyfile = f.read()
        self.run(pyfile)

    def enter_raw_repl(self):
        self.serial.write(b'\r\x03\x03') # ctrl-C twice: interrupt any running program

        self.serial.flushInput()

        self.serial.write(b'\r\x01') # ctrl-A: enter raw REPL
        sleep(.1)
        self.serial.write(b'\x04') # ctrl-D: soft reset
        sleep(.5)

    def exit_raw_repl(self):
        self.serial.write(b'\r\x02') # ctrl-B: enter friendly REPL

    def exec(self, command):
        command_bytes = command.rstrip() + b"\n\r"

        # write command
        for i in range(0, len(command_bytes), 256):
            self.serial.write(command_bytes[i:min(i + 256, len(command_bytes))])
            sleep(0.01)
        self.serial.write(b'\x04')


class SerialThread(threading.Thread):

    def __init__(self, repl, u_serial):
        super().__init__()
        self.name = "SerialThread"
        self.repl = repl
        self.u_serial = u_serial
        self.start()

    def run(self):
        logging.info('SerialThread Started')
        
        if self.u_serial.is_open():
            logging.info("Serial opened")
        else:
            logging.critical("Serial could not be open")
            return

        sleep(.2)
        self.u_serial.write(chr(4).encode())
        
        while True:
            incoming_bytes = []
            if not self.repl.send_queue.empty():
                message = self.repl.send_queue.get()
                self.u_serial.write(message)
            if self.u_serial.inWaiting():
                while self.u_serial.inWaiting():
                    incoming_bytes.append(self.u_serial.read(1))
                for index, byte in enumerate(incoming_bytes):
                    if ord(byte) < 128:
                        incoming_bytes[index] = byte.decode()
                    else:
                        incoming_bytes[index] = "$"

                incoming_message = "".join(incoming_bytes).replace("\r", "")
                self.repl.repl_text_field.insert(tk.END, incoming_message)
                self.repl.repl_text_field.see(tk.END)
                self.repl.repl_text_field.mark_set(tk.INSERT, tk.END)
                # if self.text_color == "grey":
                #     self.repl.repl_text_field.tag_add("grey", self.repl.repl_stop, tk.END)
                #     self.repl.repl_text_field.tag_config("grey", foreground="grey")
                self.repl.repl_stop = self.repl.repl_text_field.index("end-1c")
            else:
                sleep(.01)

        return


class Application(tk.Frame):
    def __init__(self, root):
        super().__init__(root)
        self.title = "MicroPython Editor"
        self.root = root
        self.change_title()
        self.grid()
        self.grid_columnconfigure(0, weight=1)

        self.editor = Editor(self)
        self.editor.grid(row=1)
    
        self.tool_bar = Toolbar(self)
        self.tool_bar.grid(row=0, sticky=tk.W)

        self.tool_bar.buttons["run"].config(command=self.editor.run_tab)
        self.tool_bar.buttons["new"].config(command=self.editor.new_tab)
        self.tool_bar.buttons["repl"].config(command=self.editor.toggle_repl)
        self.tool_bar.buttons["load_file"].config(command=self.editor.load_file)
        self.tool_bar.buttons["save_file"].config(command=self.editor.save_file)
        self.tool_bar.buttons["device"].config(command=self.editor.setup_device)

    def change_title(self, device=None):
        if device:
            self.root.title("{} - {}".format(self.title, device))
        else:
            self.root.title(self.title)

def run():
    root = tk.Tk()
    app = Application(root)
    app.mainloop()

if __name__ == "__main__":
    run()