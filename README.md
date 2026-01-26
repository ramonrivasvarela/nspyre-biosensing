#+#+#+#+------------------------------------------------------------------

# nspyre-biosensing

Lab control + experiment GUI built on top of **nspyre** (Networked Scientific Python Research Environment).

This repo contains:

- A **GUI application** ([`app.py`](app.py)) that provides instrument panels and experiment widgets
- An **instrument server** ([`inserv.py`](inserv.py)) that hosts hardware drivers over the network via nspyre
- Hardware **drivers** ([`drivers/`](drivers/)) and **experiment logic** ([`experiments/`](experiments/))

If you’re new to nspyre, the mental model is:

1. Start the data server (`nspyre-dataserv`) to store/stream datasets.
2. Start the instrument server to connect to hardware and expose it via RPC.
3. Start the GUI to control instruments and run experiments.

---

## Requirements

- **Python 3.10+** (matches nspyre’s supported baseline)
- Windows is supported (and common for NI / camera vendor SDKs)

Hardware-specific requirements vary by what you enable. Some typical ones used here:

- Signal generator control: `pyvisa` + NI-VISA (or vendor VISA)
- DLnsec delay stage: `pyserial`
- PulseStreamer: `pulsestreamer` (and the vendor backend)
- NI DAQ: `nidaqmx` + NI-DAQmx drivers installed
- Camera (optional): vendor SDK (see `inserv.py` for the currently configured camera driver)

The file [`dependencies.txt`](dependencies.txt) is a short note of the core runtime imports per instrument type.

---

## Install / Setup (Windows)

Create and activate a virtual environment, then install `nspyre` plus the instrument dependencies you need.

### 1) Create a venv

```powershell
cd path\to\nspyre-biosensing
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

### 2) Install nspyre

Option A (recommended if you just want to run):

```powershell
pip install nspyre
```

Option B (recommended if you’re editing nspyre alongside this repo):

```powershell
# from inside nspyre-biosensing
pip install -e ..\nspyre-local
```

### 3) Install instrument dependencies

Install only what you actually use (based on `instrument_activation.py` and `inserv.py`). For example:

```powershell
pip install pyvisa pyserial pulsestreamer nidaqmx
```

Optional utilities used by some helper scripts:

```powershell
pip install matplotlib
```

Note: vendor drivers (NI-DAQmx, VISA, camera SDKs) must be installed separately.

---

## Quick start

You typically run **three processes**: the data server, the instrument server, and the GUI.

### 1) Start the data server (`nspyre-dataserv`)

In a terminal:

```powershell
nspyre-dataserv
```

Notes:

- The default data server port is **30101**.
- Most experiments in this repo use `DataSource(dataset)` with defaults (connects to `localhost:30101`).
- If `nspyre-dataserv` isn’t on your PATH, use:

```powershell
python -m nspyre.cli.dataserv
```

### 2) Start the instrument server

In a terminal:

```powershell
cd path\to\nspyre-biosensing
python inserv.py
```

This script creates an `InstrumentServer` and conditionally registers drivers based on [`instrument_activation.py`](instrument_activation.py).
It then starts an interactive CLI (`serve_instrument_server_cli`) so you can inspect/control the running server.

### 3) Start the GUI

In a second terminal:

```powershell
cd path\to\nspyre-biosensing
python app.py
```

The GUI uses `InstrumentManager` to connect to the server and exposes instruments + experiment panels.

---

## Configuration

### Enable/disable hardware

Edit [`instrument_activation.py`](instrument_activation.py) to toggle which instruments are registered by `inserv.py` and cleaned up by `app.py`.

Example flags:

- `sg_activation_boolean`
- `dlnsec_activation_boolean`
- `pulser_activation_boolean`
- `xyz_activation_boolean` (NI DAQ / motion / counter)
- `camera_activation_boolean`

### Hardware addresses and ports

Edit [`inserv.py`](inserv.py) to match your lab setup:

- Signal generator VISA resource string (e.g. `TCPIP::...::INSTR`)
- Serial COM port for DLnsec (e.g. `COM3`)
- NI device name and channels (e.g. `Dev1`, `ao0/ao1/ao2`, `ctr1`, PFI lines)

The instrument names used by the GUI match the names used in `inserv.add(...)` (e.g. `sg`, `DLnsec`, `Pulser`, `DAQcontrol`, `Camera`).

---

## Logs

Both `app.py` and `inserv.py` call `nspyre_init_logger(...)` and write log files to a path relative to this repo:

- `log_path = _HERE / '../logs'`

That resolves to a sibling `logs/` directory **one level above** `nspyre-biosensing/`.
If you prefer logs inside this repo, change the log path to `_HERE / 'logs'`.

---

## Repo layout

- [`drivers/`](drivers/): hardware drivers (DAQ, pulse streamer, signal generator, camera, etc.)
- [`experiments/`](experiments/): experiment routines used by GUI widgets
- [`gui_widgets/`](gui_widgets/): PyQt/nspyre GUI panels (instruments + experiments)
- [`special_widgets/`](special_widgets/): reusable widgets (plots/heatmaps/etc.)
- [`_Evan_Examples/`](_Evan_Examples/), [`_Jacob_Examples/`](_Jacob_Examples/), [`_Uri_Examples/`](_Uri_Examples/): legacy and reference scripts

---

## Adding a new instrument (developer notes)

1. Create a driver in [`drivers/`](drivers/) (class with methods you want to expose).
2. Register it in [`inserv.py`](inserv.py) with `inserv.add(name=..., class_path=..., class_name=...)`.
3. In the GUI/experiment code, access it via `InstrumentManager` (e.g. `with InstrumentManager() as mgr: mgr.<name>...`).

---

## Troubleshooting

- **Instrument server can’t start / import errors**: install the missing Python package(s) listed in [`dependencies.txt`](dependencies.txt).
- **VISA errors**: ensure NI-VISA (or vendor VISA) is installed and the resource string in `inserv.py` matches your instrument.
- **NI-DAQ errors**: install NI-DAQmx, confirm device name (`Dev1`) in NI MAX, and update channel names/`ctr`/PFI lines.
- **COM port errors**: update `COM3` to the correct port in Windows Device Manager.
- **GUI connects but instruments are missing**: confirm the corresponding `*_activation_boolean` is `True` and restart `inserv.py`.
- **“Source failed connecting to data server”**: start `nspyre-dataserv` (default `localhost:30101`) or ensure the port isn’t blocked/in use.

---

## Safety note

This repo can directly control lab hardware. When testing new code:

- Start with instruments disabled in [`instrument_activation.py`](instrument_activation.py)
- Use conservative setpoints and verify cabling / interlocks

