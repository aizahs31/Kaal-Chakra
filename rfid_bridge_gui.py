"""
Kaal-Chakra RFID Bridge
-----------------------
RFID USB Reader -> Tkinter Game UI -> Arduino Mega

The RFID reader behaves like a USB keyboard:
    UID + Enter

The Tkinter Entry captures the UID.

Arduino receives:
    PLAYER_OK
    TASK_ASSIGNED

Files:
    players.json
    cards.json
"""

# ============================================================
# IMPORTS
# ============================================================

import json
import random
import threading
import time
import textwrap
import tkinter as tk
from tkinter import simpledialog, messagebox
from pathlib import Path

try:
    import serial
except ModuleNotFoundError:
    serial = None
from PIL import Image, ImageDraw, ImageFont, ImageTk


# ============================================================
# CONFIGURATION
# ============================================================

ARDUINO_PORT = "COM10"
BAUD_RATE = 9600

PLAYERS_FILE = Path("players.json")
CARDS_FILE = Path("cards.json")
TASK_DECK_FILE = Path("task_cards.json")
ERA_IMAGE_FILES = {
    1: Path("era_images/Indus Valley.png"),
    2: Path("era_images/Mauryan Empire.png"),
    3: Path("era_images/Gupta Empire.png"),
    4: Path("era_images/Chola Empire.png"),
    5: Path("era_images/Vijayanagar Empire.png"),
}
ERA_TEXT_COLORS = {
    # Name and score use the contrast seen in the Mauryan reference:
    # dark text on light panels, light text on dark panels.
    1: {"header": "#532116", "cloud": "#f4dfba", "task": "#532116"},
    2: {"header": "#333657", "cloud": "#333657", "task": "#f1f4fa"},
    3: {"header": "#f4e56b", "cloud": "#f4e56b", "task": "#eff7e9"},
    4: {"header": "#e1bc84", "cloud": "#e1bc84", "task": "#e1bc84"},
    5: {"header": "#f1f1f1", "cloud": "#f1f1f1", "task": "#f1f1f1"},
}

# ============================================================
# TASK DECK
# ============================================================

TASK_DECK_FILE = Path("task_cards.json")


# ============================================================
# JSON FUNCTIONS
# ============================================================

def load_json(path: Path, default):
    """Load JSON data. Return default if file doesn't exist or is invalid."""

    if not path.exists():
        return default

    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    except (json.JSONDecodeError, OSError) as e:
        print(f"Warning: Could not load {path}: {e}")
        return default


def save_json(path: Path, data):
    """Save JSON data safely."""

    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    except OSError as e:
        print(f"Error saving {path}: {e}")


# ============================================================
# MAIN GAME CLASS
# ============================================================

class GameDisplay:

    def __init__(self, root):

        self.root = root

        # ----------------------------------------------------
        # Game data
        # ----------------------------------------------------

        self.players = load_json(PLAYERS_FILE, {})
        self.cards = load_json(CARDS_FILE, {})
        self.task_deck = load_json(TASK_DECK_FILE, {})
        self.era_decks = {}

        self.last_player_uid = None
        self.scanner_buffer = ""
        self.scanner_enabled = True
        self.era_name = None

        # Prevent multiple RFID scans from being processed
        # simultaneously.
        self.processing_scan = False

        # Arduino serial connection
        self.ser = self.connect_arduino()

        # ----------------------------------------------------
        # Window
        # ----------------------------------------------------

        root.title("Kaal-Chakra")
        root.configure(bg="#0d1628")
        root.geometry("1000x650")

        self.background_image = None
        self.background_source = None
        self.background_display_size = (0, 0)
        self.background_offset = (0, 0)
        self.era_text = None
        self.player_text = None
        self.background_label = tk.Label(root, bg="#0d1628")
        self.background_label.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.background_label.lower()
        root.bind("<Configure>", self.resize_background)

        # ----------------------------------------------------
        # Default welcome screen
        # ----------------------------------------------------

        self.welcome_frame = tk.Frame(
            root,
            bg="#111d33",
            highlightbackground="#c8974b",
            highlightthickness=1
        )
        self.welcome_frame.pack(
            fill="x",
            padx=150,
            pady=(55, 25)
        )

        tk.Label(
            self.welcome_frame,
            text="KAAL-CHAKRA",
            font=("Georgia", 32, "bold"),
            fg="#e7bd72",
            bg="#111d33"
        ).pack(pady=(28, 2))

        tk.Label(
            self.welcome_frame,
            text="BHARAT THROUGH THE AGES",
            font=("Segoe UI", 11, "bold"),
            fg="#9fb6c9",
            bg="#111d33"
        ).pack()

        tk.Frame(
            self.welcome_frame,
            height=1,
            bg="#6e4b2d"
        ).pack(fill="x", padx=80, pady=20)

        tk.Label(
            self.welcome_frame,
            text="Your journey through history begins here",
            font=("Georgia", 18, "italic"),
            fg="#f2e4c7",
            bg="#111d33"
        ).pack()

        steps = tk.Frame(self.welcome_frame, bg="#111d33")
        steps.pack(pady=(22, 28))

        for number, text in (
            ("1", "Scan your player card"),
            ("2", "Scan the era card"),
            ("3", "Complete your task"),
        ):
            tk.Label(
                steps,
                text=f"{number}  {text}",
                font=("Segoe UI", 12),
                fg="#d6c5a5",
                bg="#111d33",
                anchor="w",
                width=25
            ).pack(side="left", padx=8)

        self.welcome_footer = tk.Label(
            root,
            text="RFID READY  •  A NEW CHAPTER AWAITS",
            font=("Segoe UI", 10, "bold"),
            fg="#7188a1",
            bg="#0d1628"
        )
        self.welcome_footer.pack(pady=(0, 22))

        # ----------------------------------------------------
        # Status
        # ----------------------------------------------------

        self.status_label = tk.Label(
            root,
            text="Awaiting player card",
            font=("Segoe UI", 20, "bold"),
            fg="#f2e4c7",
            bg="#111d33"
        )

        self.status_label.pack(pady=(60, 10))

        # ----------------------------------------------------
        # Player name
        # ----------------------------------------------------

        self.player_label = tk.Label(
            root,
            text="",
            font=("Georgia", 42, "bold"),
            fg="#e7bd72",
            bg="#111d33"
        )

        self.player_label.pack(pady=10)

        # ----------------------------------------------------
        # Score
        # ----------------------------------------------------

        self.score_label = tk.Label(
            root,
            text="",
            font=("Segoe UI", 16),
            fg="#b9c8d4",
            bg="#111d33"
        )

        self.score_label.pack()

        # ----------------------------------------------------
        # Task
        # ----------------------------------------------------

        self.task_label = tk.Label(
            root,
            text="",
            font=("Georgia", 22),
            fg="#e7bd72",
            bg="#111d33",
            wraplength=800,
            justify="center"
        )

        self.task_label.pack(pady=40)

        # RFID readers act like keyboards, so capture their UID globally
        # without creating a visible input widget.
        root.bind_all("<KeyPress>", self.on_keypress)

        # Initial focus
        self.root.after(
            300,
            self.focus_scanner
        )

        # ----------------------------------------------------
        # Handle window closing
        # ----------------------------------------------------

        self.root.protocol(
            "WM_DELETE_WINDOW",
            self.on_close
        )

    # ========================================================
    # FOCUS
    # ========================================================

    def focus_scanner(self):

        try:
            self.root.focus_force()

        except tk.TclError:
            pass

    def on_keypress(self, event):
        if not self.scanner_enabled:
            return

        if event.keysym == "Return":
            uid = self.scanner_buffer
            self.scanner_buffer = ""
            self.on_scan(uid=uid)
        elif event.char and event.char.isprintable():
            self.scanner_buffer += event.char

    def set_era_background(self, era):
        image_path = ERA_IMAGE_FILES.get(era)

        if image_path is None or not image_path.exists():
            self.background_source = None
            self.background_image = None
            self.background_label.config(image="", bg="#0d1628")
            print(f"No background image found for era {era}: {image_path}")
            return

        self.background_source = image_path
        self.era_text = None
        self.era_name = next(
            (
                card.get("name")
                for card in self.cards.values()
                if isinstance(card, dict) and card.get("era") == era
            ),
            None
        )
        self.status_label.pack_forget()
        self.player_label.pack_forget()
        self.score_label.pack_forget()
        self.task_label.pack_forget()
        self.resize_background()

    def clear_era_background(self):
        self.background_source = None
        self.background_image = None
        self.era_text = None
        self.player_text = None
        self.era_name = None
        self.background_label.config(image="", bg="#0d1628")

    def hide_welcome_screen(self):
        self.welcome_frame.pack_forget()
        self.welcome_footer.pack_forget()

    def resize_background(self, event=None):
        if self.background_source is None:
            return

        try:
            width = max(self.root.winfo_width(), 1)
            height = max(self.root.winfo_height(), 1)
            image = Image.open(self.background_source).convert("RGB")

            scale = min(width / image.width, height / image.height)
            size = (round(image.width * scale), round(image.height * scale))
            image = image.resize(size, Image.Resampling.LANCZOS)

            left = (width - image.width) // 2
            top = (height - image.height) // 2
            self.background_display_size = (image.width, image.height)
            self.background_offset = (left, top)
            self.draw_era_text(image)

            self.background_image = ImageTk.PhotoImage(image)
            self.background_label.config(image=self.background_image)

        except (OSError, tk.TclError) as error:
            print(f"Could not display background image: {error}")

    def draw_era_text(self, image):
        era = next(
            (
                era_id
                for era_id, path in ERA_IMAGE_FILES.items()
                if path == self.background_source
            ),
            None
        )

        if era is None:
            return

        image_width, image_height = image.size
        draw = ImageDraw.Draw(image)
        colors = ERA_TEXT_COLORS[era]

        # ============================================================
        # PANEL CENTERS
        # ============================================================

        left_x = round(image_width * 0.17)
        center_x = round(image_width * 0.50)
        right_x = round(image_width * 0.83)

        # ============================================================
        # PLAYER NAME — LEFT PANEL
        # ============================================================

        if self.player_text is not None:
            name, score = self.player_text

            name_font = self.fit_font(
                name,
                "georgiab.ttf",
                max(40, image_width // 45),
                round(image_width * 0.25)
            )

            draw.text(
                (left_x, round(image_height * 0.52)),
                name,
                font=name_font,
                fill=colors["cloud"],
                anchor="mm"
            )

        # ============================================================
        # SCORE — RIGHT PANEL
        # ============================================================

            score_font = self.load_font(
                "georgia.ttf",
                max(30, image_width // 65)
            )

            draw.text(
                (right_x, round(image_height * 0.52)),
                f"Score: {score}",
                font=score_font,
                fill=colors["cloud"],
                anchor="mm"
            )

        # ============================================================
        # TASK — CENTER PANEL
        # ============================================================

        if self.era_text is None:
            return

        title, description = self.era_text

        title_font = self.fit_font(
            title,
            "georgiab.ttf",
            max(26, round(image_width * 0.025)),
            round(image_width * 0.40)
        )

        body_font = self.load_font(
            "georgia.ttf",
            max(17, round(image_width * 0.017))
        )

        # Wrap task text
        wrapped_title = textwrap.fill(
            title,
            width=28
        )

        wrapped_description = textwrap.fill(
            description,
            width=42
        )

        # Task title
        draw.multiline_text(
            (
                center_x,
                round(image_height * 0.47)
            ),
            wrapped_title,
            font=title_font,
            fill=colors["task"],
            anchor="ma",
            align="center",
            spacing=8
        )

        # Task description
        draw.multiline_text(
            (
                center_x,
                round(image_height * 0.59)
            ),
            wrapped_description,
            font=body_font,
            fill=colors["task"],
            anchor="ma",
            align="center",
            spacing=6
        )
    @staticmethod
    def load_font(filename, size):
        try:
            return ImageFont.truetype(Path("C:/Windows/Fonts") / filename, size)
        except OSError:
            return ImageFont.load_default()

    @staticmethod
    def fit_font(text, filename, starting_size, max_width):
        size = starting_size
        while size > 40:
            font = GameDisplay.load_font(filename, size)
            if font.getbbox(text)[2] <= max_width:
                return font
            size -= 8
        return GameDisplay.load_font(filename, 40)

    def show_task_text(self, title, description):
        self.era_text = (title, description)
        self.resize_background()

    def show_player_text(self, name, score):
        self.player_text = (name, score)
        self.resize_background()

    # ========================================================
    # ARDUINO CONNECTION
    # ========================================================

    def connect_arduino(self):

        if serial is None:
            print(
                "pyserial is not installed; continuing WITHOUT Arduino connection."
            )
            return None

        try:

            ser = serial.Serial(
                ARDUINO_PORT,
                BAUD_RATE,
                timeout=1,
                write_timeout=1
            )

            # Arduino usually resets when serial connection opens.
            time.sleep(2)

            print(
                f"Connected to Arduino on {ARDUINO_PORT}"
            )

            return ser

        except Exception as e:

            print(
                f"Could not connect to Arduino on "
                f"{ARDUINO_PORT}: {e}"
            )

            print(
                "Continuing WITHOUT Arduino connection."
            )

            return None

    # ========================================================
    # SEND COMMAND TO ARDUINO
    # ========================================================

    def send_to_arduino(self, command):

        if self.ser is None:
            return

        # Run serial communication outside Tkinter's
        # main thread.
        thread = threading.Thread(
            target=self._write_worker,
            args=(command,),
            daemon=True
        )

        thread.start()

    def _write_worker(self, command):

        try:

            message = command + "\n"

            self.ser.write(
                message.encode("utf-8")
            )

            self.ser.flush()

            print(
                f"Arduino <- {command}"
            )

        except serial.SerialTimeoutException:

            print(
                f"Warning: Arduino write timed out on "
                f"{ARDUINO_PORT}"
            )

        except Exception as e:

            print(
                f"Warning: Arduino serial error: {e}"
            )

    # ========================================================
    # RFID SCAN
    # ========================================================

    def on_scan(self, event=None, uid=None):

        print(">>> ENTER PRESSED / SCAN TRIGGERED")

        if self.processing_scan:
            print(">>> Scan ignored: already processing")
            return

        uid = (self.scanner_buffer if uid is None else uid).strip()

        print(f">>> UID RECEIVED: '{uid}'")

        if not uid:
            print(">>> UID EMPTY")
            self.focus_scanner()
            return

        print(f"RFID scanned: {uid}")

        self.processing_scan = True

        try:
            self.process_card(uid)
        except Exception as e:
            print(f"ERROR while processing card {uid}: {e}")
            import traceback
            traceback.print_exc()

            self.status_label.config(
                text="Error processing card"
            )

        finally:
            self.processing_scan = False
            self.root.after(100, self.focus_scanner)
    # ========================================================
    # CARD PROCESSING
    # ========================================================

    def process_card(self, uid):

        # ----------------------------------------------------
        # NEW CARD
        # ----------------------------------------------------

        if uid not in self.cards:
            self.status_label.config(
                text=f"Unknown card: {uid}"
            )
            print(
                f"Unknown card UID: {uid}. Add it to {CARDS_FILE.name}."
            )
            return

        # ----------------------------------------------------
        # EXISTING CARD
        # ----------------------------------------------------

        card_info = self.cards.get(uid)

        # Player card
        if card_info == "player":
            self.handle_player(uid)

        # Task scanner
        elif isinstance(card_info, dict) and card_info.get("type") == "task":
            self.handle_task(uid)

        else:
            print(f"Unknown card configuration for UID {uid}: {card_info}")

    # ========================================================
    # PLAYER CARD
    # ========================================================

    def handle_player(self, uid):

        # ----------------------------------------------------
        # NEW PLAYER
        # ----------------------------------------------------

        if uid not in self.players:
            self.scanner_enabled = False

            name = simpledialog.askstring(
                "New Player",
                (
                    f"Card UID:\n\n"
                    f"{uid}\n\n"
                    "Enter player name:"
                ),
                parent=self.root
            )

            self.scanner_enabled = True

            # User cancelled
            if name is None:

                self.status_label.config(
                    text="Player registration cancelled"
                )

                return

            name = name.strip()

            # Empty name
            if not name:

                name = f"Player-{uid[-4:]}"

            # Create player
            self.players[uid] = {
                "name": name,
                "score": 0,
                "history": []
            }

            save_json(
                PLAYERS_FILE,
                self.players
            )

            print(
                f"Registered player: {name} ({uid})"
            )

        # ----------------------------------------------------
        # Set current player
        # ----------------------------------------------------

        self.last_player_uid = uid

        player = self.players[uid]

        history = player.get("history", [])
        if history:
            self.set_era_background(history[-1].get("era"))
        else:
            self.clear_era_background()

        # ----------------------------------------------------
        # Update UI
        # ----------------------------------------------------

        self.hide_welcome_screen()

        self.status_label.config(
            text="Player scanned"
        )

        self.player_label.config(
            text=player["name"]
        )

        self.score_label.config(
            text=f"Score: {player['score']}"
        )

        self.show_player_text(player["name"], player["score"])

        self.task_label.config(
            text=""
        )

        # ----------------------------------------------------
        # Tell Arduino
        # ----------------------------------------------------

        self.send_to_arduino(
            "PLAYER_OK"
        )

    # ============================================================
    # TASK CARD
    # ============================================================

    def handle_task(self, uid):

        # --------------------------------------------------------
        # No player selected
        # --------------------------------------------------------

        if self.last_player_uid is None:

            self.status_label.config(
                text="Scan a PLAYER card first!"
            )

            return

        # --------------------------------------------------------
        # Get scanner information
        # --------------------------------------------------------

        scanner = self.cards.get(uid)

        if not isinstance(scanner, dict):

            self.status_label.config(
                text="Invalid task scanner!"
            )

            return

        era = scanner.get("era")
        era_name = scanner.get("name", "Unknown Era")

        if era is None:

            self.status_label.config(
                text="Task scanner has no era!"
            )

            return

        # --------------------------------------------------------
        # Find the correct era in task_cards.json
        # --------------------------------------------------------

        eras = self.task_deck.get("eras", [])

        selected_era = None

        for era_data in eras:
            if era_data.get("id") == era:
                selected_era = era_data
                break

        # --------------------------------------------------------
        # Era not found
        # --------------------------------------------------------

        if selected_era is None:

            self.status_label.config(
                text=f"No task deck found for {era_name}"
            )

            return

        # --------------------------------------------------------
        # Get cards from this era
        # --------------------------------------------------------

        cards = selected_era.get("cards", [])

        if not cards:

            self.status_label.config(
                text=f"No tasks available for {era_name}"
            )

            return

        # --------------------------------------------------------
        # Random task
        # --------------------------------------------------------

        # Create shuffled deck for this era if it doesn't exist
        if era not in self.era_decks or not self.era_decks[era]:
            self.era_decks[era] = cards.copy()
            random.shuffle(self.era_decks[era])

        # Draw one card
        task_card = self.era_decks[era].pop()

        title = task_card.get("title", "Task")
        description = task_card.get(
            "description",
            "No description available."
        )

        effect = task_card.get(
            "effect",
            {}
        )

        # --------------------------------------------------------
        # Build display text
        # --------------------------------------------------------

        task_text = (
            f"{title}\n\n"
            f"{description}"
        )

        # --------------------------------------------------------
        # Save history
        # --------------------------------------------------------

        player = self.players[self.last_player_uid]

        player["history"].append({
            "era": era,
            "era_name": era_name,
            "card_id": task_card.get("id"),
            "title": title,
            "description": description,
            "effect": effect
        })

        save_json(
            PLAYERS_FILE,
            self.players
        )

        # --------------------------------------------------------
        # Update UI
        # --------------------------------------------------------

        self.status_label.config(
            text=f"Task assigned — {era_name}"
        )

        self.set_era_background(era)
        self.show_task_text(title, description)

        self.task_label.config(
            text="" if era == 1 else task_text
        )

        # --------------------------------------------------------
        # Tell Arduino
        # --------------------------------------------------------

        self.send_to_arduino(
            "TASK_ASSIGNED"
        )

        # --------------------------------------------------------
        # Console information
        # --------------------------------------------------------

        print()
        print("===================================")
        print("TASK ASSIGNED")
        print("===================================")
        print(f"Era: {era_name}")
        print(f"Card ID: {task_card.get('id')}")
        print(f"Title: {title}")
        print(f"Description: {description}")
        print(f"Effect: {effect}")
        print("===================================")
        print()
        
    # ========================================================
    # CLOSE PROGRAM
    # ========================================================

    def on_close(self):

            print(
                "Closing Kaal-Chakra..."
            )

            try:

                if self.ser is not None:
                    self.ser.close()

            except Exception:
                pass

            self.root.destroy()


# ============================================================
# MAIN
# ============================================================

def main():

    root = tk.Tk()

    app = GameDisplay(
        root
    )

    root.mainloop()


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    main()