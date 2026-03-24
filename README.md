# NetBox Rack to Draw.io

A Python script that visualizes a NetBox rack as a draw.io diagram.  
It displays devices with correct heights (U), colors based on side (front/rear), and additional information: device type and serial number. Full‑depth devices are shown on both sides with hatching on the opposite side.

## Features

- Fetches rack and device data from NetBox API.
- Retrieves device type details (height, full‑depth) via separate API calls.
- Supports both **front** and **rear** views, either separately or side‑by‑side.
- Full‑depth devices appear on both sides; the opposite side gets a **hatch fill** (`fillStyle=hatch`).
- Device labels contain three lines: name, device type (manufacturer + model), and serial number (if available).
- Handles self‑signed SSL certificates with `--no-verify` or custom CA bundle.
- Debug mode to inspect API responses and device processing.
- Configurable unit height (pixels) for scaling the diagram.

## Requirements

- Python 3.6+
- `requests` library

Install the required library:

```bash
pip install requests
```
## Usage

```bash
python netbox_rack_to_drawio.py <rack_url> <token> [options]
```

## Arguments
| Argument / Option        | Description |
|--------------------------|-------------|
| `rack_url`               | Full URL of the rack in NetBox API (e.g., `https://netbox.example.com/api/dcim/racks/1/`). |
| `token`                  | NetBox API token with read permissions. |
| `--side {front,rear}`    | Which side to display (default: `front`). Ignored if `--both-views` is used. |
| `--both-views`           | Display front and rear views side‑by‑side. |
| `--output`, `-o`         | Output file name (default: `rack_diagram.drawio`). |
| `--no-verify`            | Disable SSL certificate verification (use for self‑signed certificates). |
| `--ca-bundle`            | Path to a custom CA bundle file. |
| `--debug`                | Print detailed debug information (API requests, device filtering, heights, etc.). |
| `--unit-height`          | Height of one rack unit in pixels (default: `50`). |

## Examples
### Show only the front side of a rack

```bash
python netbox_rack_to_drawio.py https://netbox.example.com/api/dcim/racks/42/ abc123token
```
### Show only the rear side

```bash
python netbox_rack_to_drawio.py https://netbox.example.com/api/dcim/racks/42/ abc123token --side rear
```
### Show both front and rear side‑by‑side

```bash
python netbox_rack_to_drawio.py https://netbox.example.com/api/dcim/racks/42/ abc123token --both-views
```
### Handle a self‑signed SSL certificate

```bash
python netbox_rack_to_drawio.py https://netbox.local/api/dcim/racks/42/ abc123token --no-verify
```
### Debug mode (to see why some devices are skipped)

```bash
python netbox_rack_to_drawio.py https://netbox.example.com/api/dcim/racks/42/ abc123token --debug
```

## Notes
* The script expects the NetBox API to be reachable and the token to have sufficient permissions.

* If a device has no position or device_type, it will be skipped (visible in debug mode).

* The height of a device is taken from device_type.u_height. If that field is missing, the device is skipped.

* Full‑depth devices are recognized by device_type.is_full_depth. If a device is full‑depth but has no face set, it appears on both sides without hatching (no clear opposite).

* The generated .drawio file can be opened in diagrams.net (formerly draw.io).

## Troubleshooting
* SSL errors: use --no-verify or provide your CA bundle with --ca-bundle.

* No devices shown: run with --debug to see why devices are filtered out (missing position, wrong side, no device type, no u_height).

* Hatching not visible: ensure your draw.io version supports fillStyle=hatch. You can modify the hatchColor in the script if needed.

* Incorrect device heights: verify that u_height is set in NetBox device types. The script no longer parses height from the model name.
