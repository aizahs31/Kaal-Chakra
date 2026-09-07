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
# TCL / TK FIX FOR THIS WINDOWS PYTHON INSTALLATION
# ============================================================

import os

os.environ["TCL_LIBRARY"] = (
    r"C:\Users\Shazia\AppData\Local\Programs\Python\Python313\tcl\tcl8.6"
)

os.environ["TK_LIBRARY"] = (
    r"C:\Users\Shazia\AppData\Local\Programs\Python\Python313\tcl\tk8.6"
)

# ============================================================
# IMPORTS
# ============================================================

import json
import random
import threading
import time
import tkinter as tk
from tkinter import simpledialog, messagebox
from pathlib import Path

import serial


# ============================================================
# CONFIGURATION
# ============================================================

ARDUINO_PORT = "COM10"
BAUD_RATE = 9600

PLAYERS_FILE = Path("players.json")
CARDS_FILE = Path("cards.json")
TASK_DECK_FILE = Path("task_cards.json")

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

        # Prevent multiple RFID scans from being processed
        # simultaneously.
        self.processing_scan = False

        # Arduino serial connection
        self.ser = self.connect_arduino()

        # ----------------------------------------------------
        # Window
        # ----------------------------------------------------

        root.title("Kaal-Chakra")
        root.configure(bg="#2e2e1a")
        root.geometry("900x500")

        # ----------------------------------------------------
        # Status
        # ----------------------------------------------------

        self.status_label = tk.Label(
            root,
            text="Scan a player card to begin",
            font=("Segoe UI", 22),
            fg="#eaeaea",
            bg="#1a1a2e"
        )

        self.status_label.pack(pady=(60, 10))

        # ----------------------------------------------------
        # Player name
        # ----------------------------------------------------

        self.player_label = tk.Label(
            root,
            text="",
            font=("Segoe UI", 48, "bold"),
            fg="#f5c518",
            bg="#1a1a2e"
        )

        self.player_label.pack(pady=10)

        # ----------------------------------------------------
        # Score
        # ----------------------------------------------------

        self.score_label = tk.Label(
            root,
            text="",
            font=("Segoe UI", 20),
            fg="#aaaaaa",
            bg="#1a1a2e"
        )

        self.score_label.pack()

        # ----------------------------------------------------
        # Task
        # ----------------------------------------------------

        self.task_label = tk.Label(
            root,
            text="",
            font=("Segoe UI", 26),
            fg="#4ade80",
            bg="#1a1a2e",
            wraplength=800,
            justify="center"
        )

        self.task_label.pack(pady=40)

        # ----------------------------------------------------
        # RFID input
        # ----------------------------------------------------
        #
        # The RFID reader behaves like a keyboard.
        #
        # Example:
        #
        #   RFID scans:
        #       0755599857
        #
        #   Reader sends:
        #       0755599857 + Enter
        #
        # ----------------------------------------------------

        self.entry = tk.Entry(
            root,
            font=("Segoe UI", 12)
        )

        # Keep it technically visible but unobtrusive.
        self.entry.place(
            x=5,
            y=5,
            width=150,
            height=25
        )

        self.entry.bind(
            "<Return>",
            self.on_scan
        )

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
            self.entry.config(state="normal")
            self.entry.focus_set()
            self.entry.icursor(tk.END)

        except tk.TclError:
            pass

    # ========================================================
    # ARDUINO CONNECTION
    # ========================================================

    def connect_arduino(self):

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

    def on_scan(self, event=None):

        print(">>> ENTER PRESSED / SCAN TRIGGERED")

        if self.processing_scan:
            print(">>> Scan ignored: already processing")
            return

        uid = self.entry.get().strip()

        print(f">>> UID RECEIVED: '{uid}'")

        self.entry.delete(0, tk.END)

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

            # Disable RFID input while registration dialog
            # is open.
            self.entry.config(
                state="disabled"
            )

            kind = simpledialog.askstring(
                "New Card",
                (
                    f"Card UID:\n\n"
                    f"{uid}\n\n"
                    "Enter card type:\n"
                    "player or task"
                ),
                parent=self.root
            )

            # Re-enable input.
            self.entry.config(
                state="normal"
            )

            # ------------------------------------------------
            # User cancelled
            # ------------------------------------------------

            if kind is None:

                self.status_label.config(
                    text="Card registration cancelled"
                )

                return

            kind = kind.strip().lower()

            # ------------------------------------------------
            # Validate type
            # ------------------------------------------------

            if kind.startswith("p"):

                self.cards[uid] = "player"

            elif kind.startswith("t"):

                self.cards[uid] = "task"

            else:

                messagebox.showwarning(
                    "Invalid Card Type",
                    "Please enter either 'player' or 'task'.",
                    parent=self.root
                )

                return

            # Save card
            save_json(
                CARDS_FILE,
                self.cards
            )

            print(
                f"Registered {uid} as {self.cards[uid]}"
            )

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

            self.entry.config(
                state="disabled"
            )

            name = simpledialog.askstring(
                "New Player",
                (
                    f"Card UID:\n\n"
                    f"{uid}\n\n"
                    "Enter player name:"
                ),
                parent=self.root
            )

            self.entry.config(
                state="normal"
            )

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

        # ----------------------------------------------------
        # Update UI
        # ----------------------------------------------------

        self.status_label.config(
            text="Player scanned"
        )

        self.player_label.config(
            text=player["name"]
        )

        self.score_label.config(
            text=f"Score: {player['score']}"
        )

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

        self.task_label.config(
            text=task_text
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