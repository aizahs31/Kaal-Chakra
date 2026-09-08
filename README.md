# Kaal-Chakra

> An RFID-powered educational game that takes players through the history of India, from the Indus Valley Civilization to the Vijayanagara Empire.

Kaal-Chakra connects an RFID reader, a Tkinter desktop interface, and an Arduino Mega. A player scans their card, then scans an era card to receive a randomly selected historical task. The application renders the active era artwork, player information, and task content in a themed interface.

## Features

- RFID reader support through keyboard-style UID input.
- Player registration and persistent player history.
- Five historical era task decks.
- Random task selection with per-era shuffled decks.
- Era-specific artwork and text styling.
- Player name and score display.
- Task history saved to JSON.
- Optional Arduino serial notifications.
- Graceful operation without an Arduino connection.
- Responsive image scaling when the window is resized.

## Era Coverage

| Era | Era card UID | Artwork |
|---|---:|---|
| Indus Valley Civilization | `0755599857` | [Indus Valley.png](era_images/Indus%20Valley.png) |
| Mauryan Empire | `0756668817` | [Mauryan Empire.png](era_images/Mauryan%20Empire.png) |
| Gupta Empire | `0756314881` | [Gupta Empire.png](era_images/Gupta%20Empire.png) |
| Chola Empire | `0756451857` | [Chola Empire.png](era_images/Chola%20Empire.png) |
| Vijayanagara Empire | `0756706257` | [Vijayanagar Empire.png](era_images/Vijayanagar%20Empire.png) |

The task deck contains **75 cards**, with **15 cards per era**.

## Screenshots and Artwork

The application uses the following artwork as its era-specific game screens:

### Indus Valley Civilization

![Indus Valley Civilization interface artwork](era_images/Indus%20Valley.png)

### Mauryan Empire

![Mauryan Empire interface artwork](era_images/Mauryan%20Empire.png)

### Gupta Empire

![Gupta Empire interface artwork](era_images/Gupta%20Empire.png)

### Chola Empire

![Chola Empire interface artwork](era_images/Chola%20Empire.png)

### Vijayanagara Empire

![Vijayanagara Empire interface artwork](era_images/Vijayanagar%20Empire.png)

## Requirements

- Windows 10 or later.
- Python 3.10 or later.
- Tkinter, normally included with the official Windows Python installer.
- Pillow for image rendering.
- pyserial for Arduino communication.
- A keyboard-emulating RFID reader.
- Optional: Arduino Mega connected over USB.

## Installation

Open PowerShell in the project directory:

```powershell
cd D:\User\Desktop\SIH\Kaal-Chakra
```

Install the Python dependencies into the interpreter you will use to run the application:

```powershell
python -m pip install Pillow pyserial
```

You can also use the Python launcher consistently:

```powershell
py -m pip install Pillow pyserial
```

Check the installation:

```powershell
python -c "import tkinter, serial; from PIL import Image; print('Dependencies ready')"
```

> Use the same command family for installation and execution. For example, if you run the program with `python`, install packages with `python -m pip`. If you run it with `py`, use `py -m pip`.

## Running the Application

```powershell
cd D:\User\Desktop\SIH\Kaal-Chakra
python rfid_bridge_gui.py
```

Or:

```powershell
py rfid_bridge_gui.py
```

The application opens as a desktop window. The RFID reader must be connected and focused on the application window before scanning.

## Game Workflow

1. Start the application.
2. Scan a registered player card.
3. Scan the task card for the desired historical era.
4. The application selects a random card from that era's deck.
5. The player name and score are rendered in the era artwork's player area.
6. The task title and description are rendered in the task panel.
7. The task is appended to the player's history in `players.json`.
8. Arduino receives a notification when configured.

For a quick test without physical cards, use a keyboard and type a UID followed by Enter while the application is focused.

### Example Test Sequence

```text
Player UID: 1239257449
Indus task UID: 0755599857
```

The player card must be scanned before the task card. The program rejects unknown UIDs instead of opening a registration dialog.

## RFID and Arduino Integration

The RFID reader is expected to behave like a USB keyboard:

```text
UID + Enter
```

The application captures the keyboard input globally and processes the UID when Enter is received.

Arduino configuration is defined near the top of `rfid_bridge_gui.py`:

```python
ARDUINO_PORT = "COM10"
BAUD_RATE = 9600
```

Change `ARDUINO_PORT` to the COM port shown in Windows Device Manager if necessary.

The application sends these newline-terminated commands:

| Command | Sent when |
|---|---|
| `PLAYER_OK` | A registered player card is scanned successfully. |
| `TASK_ASSIGNED` | A task card produces a task successfully. |

If the Arduino is disconnected, the interface continues running and logs a warning instead of stopping.

## Project Structure

```text
Kaal-Chakra/
├── rfid_bridge_gui.py       # Main desktop application
├── cards.json               # RFID UID to player/task-card mapping
├── players.json             # Player profiles, scores, and task history
├── task_cards.json          # Game metadata and 75 historical task cards
├── era_images/              # Era-specific UI artwork
│   ├── Indus Valley.png
│   ├── Mauryan Empire.png
│   ├── Gupta Empire.png
│   ├── Chola Empire.png
│   └── Vijayanagar Empire.png
└── README.md
```

## Data Files

### `cards.json`

Maps scanned UIDs to either a player card or a task scanner:

```json
{
  "1239257449": "player",
  "0755599857": {
    "type": "task",
    "era": 1,
    "name": "Indus Valley Civilization"
  }
}
```

### `players.json`

Stores player profiles and task history:

```json
{
  "1239257449": {
    "name": "Shazia",
    "score": 0,
    "history": []
  }
}
```

The application writes task records to the player's `history` list after a task is assigned.

### `task_cards.json`

Contains the game metadata and the task decks grouped by era. Each task can define an effect such as:

- `move`
- `collect`
- `pay`
- `dice`
- `multiple`
- `skip_turn`
- `choice`

The application currently displays and records effects. It does not automatically apply movement, currency, dice, or score changes.

## Configuration

The main settings are in `rfid_bridge_gui.py`:

```python
ARDUINO_PORT = "COM10"
BAUD_RATE = 9600
PLAYERS_FILE = Path("players.json")
CARDS_FILE = Path("cards.json")
TASK_DECK_FILE = Path("task_cards.json")
```

Run the program from the project directory so these relative JSON and image paths resolve correctly.

## Troubleshooting

### `ModuleNotFoundError: No module named 'serial'`

Install `pyserial` into the same Python interpreter used to launch the application:

```powershell
python -m pip install pyserial
```

If you run the app with `py`, use:

```powershell
py -m pip install pyserial
```

### `ModuleNotFoundError: No module named 'PIL'`

Install Pillow:

```powershell
python -m pip install Pillow
```

### Arduino connection warning

Confirm the Arduino is connected, identify its COM port in Device Manager, and update `ARDUINO_PORT`. The application can still be tested without Arduino hardware.

### Unknown card UID

The UID is not present in `cards.json`. Confirm the reader output and add the UID to the file with the correct player or era-card structure.

### Tkinter or Tcl/Tk error

Do not hard-code another user's `TCL_LIBRARY` or `TK_LIBRARY` paths. The official Windows Python installer normally provides the correct Tcl/Tk files automatically. Verify Tkinter with:

```powershell
python -c "import tkinter as tk; root=tk.Tk(); root.destroy(); print('Tkinter ready')"
```

### Artwork does not appear

Run the application from the project root:

```powershell
cd D:\User\Desktop\SIH\Kaal-Chakra
python rfid_bridge_gui.py
```

Also confirm that the five files in `era_images` retain their exact names.

## Development Checks

Compile the main script without launching the GUI:

```powershell
python -m py_compile rfid_bridge_gui.py
```

Check the file with the selected Python environment before committing changes.

## Current Scope and Future Enhancements

The current application is an RFID bridge and task-display interface. Possible future enhancements include:

- Applying task effects to player movement and currency automatically.
- Updating scores from task outcomes.
- Adding an administrator screen for card registration.
- Adding a reset or new-game workflow.
- Moving configuration to a separate settings file.
- Adding automated tests for JSON loading, card processing, and task selection.
- Including the Arduino firmware in this repository.

## License

No license file is currently included in this repository. Add a license before distributing the project publicly.
