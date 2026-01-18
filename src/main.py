import tkinter as tk
from tkinter import messagebox, ttk
import json
import os
import sys
import subprocess
import requests
import threading
import time
from datetime import datetime
import pystray
from PIL import Image, ImageDraw
import win32gui 
import win32process

# --- Path Management ---
def get_app_data_path(filename):
    app_data = os.getenv('LOCALAPPDATA')
    config_dir = os.path.join(app_data, APP_NAME)
    if not os.path.exists(config_dir):
        try:
            os.makedirs(config_dir)
        except OSError:
            pass 
    return os.path.join(config_dir, filename)

CONFIG_FILE = get_app_data_path("config.json")
STATS_FILE = get_app_data_path("stats.json")
QUEUE_FILE = get_app_data_path("queue.json")

# --- Config Management ---
def load_config():
    default_gas_url = "https://script.google.com/macros/s/AKfycbyyN39lbyWLoSzs5NkT70b-ZAga9NXCag8C-D7DXNXsaoviP_hcR2fUJKTfaoC1PFHa/exec"
    default_config = {
        "user_name": "Unknown User", 
        "gas_url": default_gas_url, 
        "is_locked": False,
        "auto_hide_whatsapp": False,
        "geometry": "60x140+100+100"
    }

    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
                for k, v in default_config.items():
                    if k not in config:
                        config[k] = v
                return config
        except:
            pass
    return default_config

def save_config(config):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"Error saving config: {e}")

# --- Stats Management (Daily Counter) ---
def load_stats():
    today_str = datetime.now().strftime("%Y-%m-%d")
    default_stats = {"date": today_str, "counts": {}}
    
    if os.path.exists(STATS_FILE):
        try:
            with open(STATS_FILE, "r", encoding="utf-8") as f:
                stats = json.load(f)
                # Reset if date changed
                if stats.get("date") != today_str:
                    return default_stats
                return stats
        except:
            pass
    return default_stats

def save_stats(stats):
    try:
        with open(STATS_FILE, "w", encoding="utf-8") as f:
            json.dump(stats, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"Error saving stats: {e}")

# --- Offline Queue Management ---
def add_to_queue(data):
    queue = []
    if os.path.exists(QUEUE_FILE):
        try:
            with open(QUEUE_FILE, "r", encoding="utf-8") as f:
                queue = json.load(f)
        except:
            pass
    queue.append(data)
    with open(QUEUE_FILE, "w", encoding="utf-8") as f:
        json.dump(queue, f, ensure_ascii=False, indent=4)
    print(f"Added to offline queue. Total: {len(queue)}")

def process_queue_thread(gas_url):
    """Background thread to process offline queue"""
    while True:
        if os.path.exists(QUEUE_FILE):
            queue = []
            try:
                with open(QUEUE_FILE, "r", encoding="utf-8") as f:
                    queue = json.load(f)
            except:
                pass
            
            if queue and gas_url:
                data = queue[0] # Try first item
                try:
                    print("Attempting to resend offline data...")
                    response = requests.post(gas_url, json=data, timeout=10)
                    if response.status_code == 200:
                        # Success: Remove from queue
                        queue.pop(0)
                        with open(QUEUE_FILE, "w", encoding="utf-8") as f:
                            json.dump(queue, f, ensure_ascii=False, indent=4)
                        print("Resend success!")
                    else:
                        print(f"Resend failed: {response.status_code}")
                except Exception as e:
                    print(f"Resend connection error: {e}")
            
        time.sleep(10) # Check every 10 seconds

# --- Modern Button Class ---
class ModernButton(tk.Button):
    def __init__(self, parent, text, bg_color, hover_color, **kwargs):
        super().__init__(parent, text=text, bg=bg_color, relief="flat", bd=0, 
                         activebackground=hover_color, activeforeground=kwargs.get("fg", "black"), 
                         cursor="hand2", **kwargs)
        self.bg_color = bg_color
        self.hover_color = hover_color
        self.bind("<Enter>", self.on_enter)
        self.bind("<Leave>", self.on_leave)

    def on_enter(self, e):
        self["bg"] = self.hover_color

    def on_leave(self, e):
        self["bg"] = self.bg_color

# --- Main App Class ---
class ClickCounterApp:
    def __init__(self, root):
        self.root = root
        self.config = load_config()
        self.stats = load_stats()
        
        self.is_locked = self.config.get("is_locked", False)
        self.auto_hide_whatsapp = self.config.get("auto_hide_whatsapp", False)
        
        # Variables
        self.current_popup = None
        self.active_menu_name = None
        self.last_popup_close_time = 0
        self.is_visible = True
        
        # 1. Window Setup
        self.root.overrideredirect(True)
        self.root.attributes("-alpha", 0.75)
        self.root.attributes("-topmost", True)
        self.root.config(bg="white")
        
        # Restore position
        geo = self.config.get("geometry", "60x140+100+100")
        try:
            self.root.geometry(geo)
        except:
            self.root.geometry("60x140+100+100")

        # Dragging Logic
        self._offsetx = 0
        self._offsety = 0
        self.root.bind('<Button-1>', self.clickwin)
        self.root.bind('<B1-Motion>', self.dragwin)
        self.root.bind('<ButtonRelease-1>', self.save_geometry_if_changed)

        # UI Setup
        self.setup_ui()
        
        # Start Background Tasks
        threading.Thread(target=self.setup_system_tray, daemon=True).start()
        threading.Thread(target=self.monitor_focus, daemon=True).start()
        
        # Start Offline Queue Processor
        if self.config.get("gas_url"):
            threading.Thread(target=process_queue_thread, args=(self.config["gas_url"],), daemon=True).start()

        if UPDATE_CHECK_URL:
            threading.Thread(target=self.check_for_updates, daemon=True).start()

    def clickwin(self, event):
        self._offsetx = event.x
        self._offsety = event.y
        self.close_popup()

    def dragwin(self, event):
        if not self.is_locked:
            x = self.root.winfo_x() + event.x - self._offsetx
            y = self.root.winfo_y() + event.y - self._offsety
            self.root.geometry(f'+{x}+{y}')

    def save_geometry_if_changed(self, event=None):
        current_geo = self.root.geometry()
        if current_geo != self.config.get("geometry"):
            self.config["geometry"] = current_geo
            save_config(self.config)

    def setup_ui(self):
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)

        # Action Button (⚡)
        self.btn_actions = ModernButton(
            self.root, text="⚡", font=("Segoe UI Emoji", 20),
            bg_color="white", hover_color="#e0e0e0", fg="#2980b9",
            command=lambda: self.handle_menu_click("Actions")
        )
        self.btn_actions.grid(row=0, column=0, sticky="nsew", padx=1, pady=1)

        # Wins Button (🏆)
        self.btn_wins = ModernButton(
            self.root, text="🏆", font=("Segoe UI Emoji", 20),
            bg_color="white", hover_color="#e0e0e0", fg="#f39c12",
            command=lambda: self.handle_menu_click("Wins")
        )
        self.btn_wins.grid(row=1, column=0, sticky="nsew", padx=1, pady=1)

        # Resize Grip
        self.resize_grip = tk.Label(self.root, text="◢", bg="white", fg="#bdc3c7", cursor="sizing")
        self.resize_grip.place(relx=1.0, rely=1.0, anchor="se")
        self.resize_grip.bind("<Button-1>", self.start_resize)
        self.resize_grip.bind("<B1-Motion>", self.perform_resize)
        self.resize_grip.bind("<ButtonRelease-1>", self.save_geometry_if_changed)

    # --- Updater Logic ---
    def check_for_updates(self):
        try:
            response = requests.get(UPDATE_CHECK_URL, timeout=5)
            if response.status_code == 200:
                data = response.json()
                latest_version = data.get("version")
                download_url = data.get("url")
                if latest_version and latest_version > VERSION:
                    self.root.after(0, lambda: self.prompt_update(latest_version, download_url))
        except:
            pass

    def prompt_update(self, version, url):
        if messagebox.askyesno("Update Available", f"New version {version} available.\nUpdate now?"):
            threading.Thread(target=self.perform_update, args=(url,), daemon=True).start()

    def perform_update(self, url):
        try:
            new_exe_name = "ClickCounter_new.exe"
            response = requests.get(url, stream=True)
            with open(new_exe_name, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            current_exe = sys.executable
            batch_script = f"""
@echo off
timeout /t 1 /nobreak > NUL
taskkill /F /PID {os.getpid()}
del "{current_exe}"
ren "{new_exe_name}" "{os.path.basename(current_exe)}"
start "" "{current_exe}"
del "%~f0"
            """
            with open("update.bat", "w") as f:
                f.write(batch_script)
            subprocess.Popen("update.bat", shell=True)
            self.root.quit()
        except:
            pass

    # --- Focus Monitoring ---
    def monitor_focus(self):
        while True:
            if self.auto_hide_whatsapp:
                try:
                    hwnd = win32gui.GetForegroundWindow()
                    title = win32gui.GetWindowText(hwnd).lower()
                    is_target_app = "whatsapp" in title or "line" in title
                    
                    try:
                        _, pid = win32process.GetWindowThreadProcessId(hwnd)
                        is_me = (pid == os.getpid())
                    except:
                        is_me = False

                    should_show = is_target_app or is_me

                    if should_show and not self.is_visible:
                        self.root.after(0, self.root.deiconify)
                        if self.current_popup:
                            self.root.after(0, self.current_popup.deiconify)
                        self.is_visible = True
                        
                    elif not should_show and self.is_visible:
                        self.root.after(0, self.root.withdraw)
                        if self.current_popup:
                            self.root.after(0, self.current_popup.withdraw)
                        self.is_visible = False
                except:
                    pass
            else:
                if not self.is_visible:
                    self.root.after(0, self.root.deiconify)
                    self.is_visible = True
            time.sleep(0.5)

    # --- Resizing Logic ---
    def start_resize(self, event):
        self._resize_start_x = event.x_root
        self._resize_start_y = event.y_root
        self._win_start_w = self.root.winfo_width()
        self._win_start_h = self.root.winfo_height()

    def perform_resize(self, event):
        if not self.is_locked:
            delta_x = event.x_root - self._resize_start_x
            delta_y = event.y_root - self._resize_start_y
            new_w = max(40, self._win_start_w + delta_x)
            new_h = max(80, self._win_start_h + delta_y)
            self.root.geometry(f"{new_w}x{new_h}")

    # --- Popup Logic (With Correction Button) ---
    def handle_menu_click(self, menu_name):
        if self.active_menu_name == menu_name:
            self.close_popup()
            return
        if (time.time() - self.last_popup_close_time) < 0.2:
            return
        self.show_popup(menu_name)

    def show_popup(self, menu_name):
        self.close_popup()
        
        popup = tk.Toplevel(self.root)
        popup.overrideredirect(True)
        popup.attributes("-topmost", True)
        popup.config(bg="white", bd=1, relief="solid")
        
        self.root.update_idletasks()
        root_x = self.root.winfo_rootx()
        root_y = self.root.winfo_rooty()
        root_w = self.root.winfo_width()
        root_h = self.root.winfo_height()
        
        screen_w = self.root.winfo_screenwidth()
        if root_x + root_w + 250 > screen_w:
            pos_x = root_x - 255
        else:
            pos_x = root_x + root_w + 5
            
        if menu_name == "Actions":
            pos_y = root_y
        else:
            pos_y = root_y + (root_h // 2)

        pos_y = max(0, pos_y)
        popup.geometry(f"250x240+{int(pos_x)}+{int(pos_y)}")

        tk.Label(popup, text=menu_name.upper(), bg="white", fg="#7f8c8d", 
                 font=("Arial", 10, "bold"), pady=5).pack(fill=tk.X)

        items = []
        if menu_name == "Actions":
            items = [
                "Clients Called", "Clients Discussed on WhatsApp", 
                "Potential Partners Contacted", "Updated Teasers", 
                "Updated Catalogs", "Events"
            ]
            color = "#3498db"
        else:
            items = [
                "Client Booked", "5-Star Review", 
                "Partnership Finalized", "Catalogs Finalized"
            ]
            color = "#27ae60"

        # Update stats date check before rendering
        self.stats = load_stats()

        for item in items:
            # ใช้ Frame เพื่อจัดเรียง [ชื่อ (count)] [ -1 ]
            row_frame = tk.Frame(popup, bg="white")
            row_frame.pack(fill=tk.X, padx=0, pady=0)

            count = self.stats["counts"].get(item, 0)
            
            # ปุ่มหลัก (Main Button) +1
            btn_text = f"{item} ({count})"
            btn_main = tk.Button(row_frame, text=btn_text, bg="white", fg="black", bd=0, anchor="w",
                                activebackground=color, activeforeground="white", padx=10, pady=5,
                                command=lambda i=item: [self.log_data(menu_name, i, 1), self.close_popup()])
            btn_main.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

            # ปุ่มลบ (Correction Button) -1
            btn_neg = tk.Button(row_frame, text="-1", bg="#ecf0f1", fg="#c0392b", bd=0, width=4,
                               activebackground="#e74c3c", activeforeground="white",
                               command=lambda i=item: [self.log_data(menu_name, i, -1), self.close_popup()])
            btn_neg.pack(side=tk.RIGHT, fill=tk.Y)
            
            # Hover Effects
            def on_enter_row(e, b1=btn_main, b2=btn_neg):
                b1.config(bg="#f5f6fa")
                b2.config(bg="#dfe6e9")
            def on_leave_row(e, b1=btn_main, b2=btn_neg):
                b1.config(bg="white")
                b2.config(bg="#ecf0f1")
                
            btn_main.bind("<Enter>", on_enter_row)
            btn_main.bind("<Leave>", on_leave_row)
            btn_neg.bind("<Enter>", on_enter_row) # ให้ปุ่มลบมีผลกับปุ่มหลักด้วยหรือไม่ก็ได้

        popup.lift()
        self.current_popup = popup
        self.active_menu_name = menu_name
        
        popup.after(300, lambda: self._safe_bind_focus(popup))

    def _safe_bind_focus(self, popup):
        if self.current_popup == popup:
            popup.focus_force()
            popup.bind("<FocusOut>", self.on_focus_out)

    def on_focus_out(self, event):
        if self.current_popup:
            focused = self.root.focus_get()
            if focused is None or str(focused).find(str(self.current_popup)) == -1:
                self.close_popup()

    def close_popup(self):
        if self.current_popup:
            self.last_popup_close_time = time.time()
            try:
                self.current_popup.destroy()
            except:
                pass
            self.current_popup = None
            self.active_menu_name = None

    def log_data(self, menu, action, count_val):
        # 1. Update UI Counter (Stats) Immediately
        current_count = self.stats["counts"].get(action, 0)
        new_count = current_count + count_val
        self.stats["counts"][action] = new_count
        save_stats(self.stats)

        # 2. Prepare Data
        now = datetime.now()
        data = {
            "date": now.strftime("%Y-%m-%d"),
            "timestamp": now.strftime("%H:%M:%S"),
            "user_name": self.config.get("user_name", "Unknown"),
            "menu": menu,
            "action": action,
            "counts": count_val, # Send 1 or -1
            "details": ""   
        }
        
        self.blink_effect(count_val)
        
        # 3. Send Data (Try Online -> If fail -> Queue)
        threading.Thread(target=self.send_or_queue, args=(data,), daemon=True).start()

    def blink_effect(self, count_val):
        original_bg = self.root["bg"]
        color = "#2ecc71" if count_val > 0 else "#e74c3c" # Green for +1, Red for -1
        self.root.config(bg=color)
        self.root.after(200, lambda: self.root.config(bg=original_bg))

    def send_or_queue(self, data):
        url = self.config.get("gas_url", "")
        if not url:
            return
        
        success = False
        try:
            response = requests.post(url, json=data, timeout=5)
            if response.status_code == 200:
                success = True
                print("Sent successfully")
        except Exception as e:
            print(f"Send failed: {e}")
        
        if not success:
            add_to_queue(data)

    # --- System Tray & Settings ---
    def setup_system_tray(self):
        image = Image.new('RGB', (64, 64), color=(255, 255, 255))
        d = ImageDraw.Draw(image)
        d.ellipse((16, 16, 48, 48), fill=(41, 128, 185))
        
        def on_toggle_lock(icon, item):
            self.is_locked = not self.is_locked
            self.config["is_locked"] = self.is_locked
            save_config(self.config)
            
        def on_toggle_auto_hide(icon, item):
            self.auto_hide_whatsapp = not self.auto_hide_whatsapp
            self.config["auto_hide_whatsapp"] = self.auto_hide_whatsapp
            save_config(self.config)

        def on_settings(icon, item):
            self.root.after(0, self.open_settings)

        def on_exit(icon, item):
            icon.stop()
            self.root.after(0, self.close_app)

        menu = pystray.Menu(
            pystray.MenuItem(f'Version {VERSION}', lambda i, k: None, enabled=False),
            pystray.MenuItem('Settings', on_settings),
            pystray.MenuItem('Lock Position', on_toggle_lock, checked=lambda item: self.is_locked),
            pystray.MenuItem('Auto-hide (WhatsApp/LINE)', on_toggle_auto_hide, checked=lambda item: self.auto_hide_whatsapp),
            pystray.MenuItem('Exit', on_exit)
        )

        self.tray_icon = pystray.Icon("click_counter", image, "Click Counter", menu)
        self.tray_icon.run()

    def open_settings(self):
        settings_win = tk.Toplevel(self.root)
        settings_win.title("Settings")
        settings_win.geometry("300x200")
        settings_win.attributes("-topmost", True)
        
        tk.Label(settings_win, text="User Name:").pack(pady=(10,0))
        name_entry = tk.Entry(settings_win, width=30)
        name_entry.insert(0, self.config.get("user_name", ""))
        name_entry.pack(pady=5)
        
        tk.Label(settings_win, text="GAS Web App URL:").pack(pady=(10,0))
        url_entry = tk.Entry(settings_win, width=30)
        url_entry.insert(0, self.config.get("gas_url", ""))
        url_entry.pack(pady=5)
        
        def save_and_close():
            self.config["user_name"] = name_entry.get()
            self.config["gas_url"] = url_entry.get()
            save_config(self.config)
            settings_win.destroy()
            
        tk.Button(settings_win, text="Save", command=save_and_close).pack(pady=20)

    def close_app(self):
        self.config["geometry"] = self.root.geometry()
        save_config(self.config)
        self.root.destroy()
        os._exit(0)

if __name__ == "__main__":
    root = tk.Tk()
    app = ClickCounterApp(root)
    root.mainloop()