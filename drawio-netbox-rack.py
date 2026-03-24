#!/usr/bin/env python3
"""
Визуализация стойки NetBox в draw.io:
- full‑depth устройства отображаются на обеих сторонах,
- на противоположной стороне – штриховка,
- цвета: front – #d0e0f0, rear – #f0e0d0,
- имя, тип, серийный номер – отдельными строками.
"""

import argparse
import requests
import xml.etree.ElementTree as ET
from xml.dom import minidom
import sys
import re
import urllib3
import json

def html_escape(text):
    if not text:
        return ""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def fetch_rack_data(session, rack_url):
    response = session.get(rack_url)
    try:
        return response.json()
    except json.JSONDecodeError:
        print(f"Ошибка JSON. Статус: {response.status_code}\n{response.text[:500]}", file=sys.stderr)
        raise

def fetch_devices_in_rack(session, rack_id, base_url):
    devices_url = f"{base_url}/api/dcim/devices/?rack_id={rack_id}"
    devices = []
    while devices_url:
        resp = session.get(devices_url)
        resp.raise_for_status()
        data = resp.json()
        devices.extend(data['results'])
        devices_url = data['next']
    return devices

def enrich_device_types(session, devices, base_url, debug=False):
    """Подгружаем полные данные типов устройств (u_height, is_full_depth)."""
    cache = {}
    for dev in devices:
        dt = dev.get('device_type')
        if not dt:
            continue
        if isinstance(dt, dict):
            dt_url = dt.get('url')
            if not dt_url and dt.get('id'):
                dt_url = f"{base_url}/api/dcim/device-types/{dt['id']}/"
        elif isinstance(dt, str):
            dt_url = dt
        else:
            continue

        if dt_url in cache:
            dev['device_type'] = cache[dt_url]
            continue

        if debug:
            print(f"Загрузка device_type: {dt_url}")
        try:
            resp = session.get(dt_url)
            resp.raise_for_status()
            full_dt = resp.json()
            cache[dt_url] = full_dt
            dev['device_type'] = full_dt
            if debug:
                print(f"  u_height={full_dt.get('u_height')}, full_depth={full_dt.get('is_full_depth', False)}")
        except Exception as e:
            print(f"Ошибка загрузки device_type {dt_url}: {e}", file=sys.stderr)

def get_face_value(face_field):
    if isinstance(face_field, dict):
        return face_field.get('value')
    return face_field

def build_side_data(devices, u_height, side, desc_units=False, debug=False):
    """
    Возвращает список устройств для указанной стороны (front/rear).
    Если устройство full-depth, оно включается в обе стороны.
    Для стороны, не совпадающей с face, добавляется флаг 'is_opposite_side'.
    """
    side_devices = []
    for dev in devices:
        name = dev.get('name')
        position = dev.get('position')
        face = get_face_value(dev.get('face'))
        if position is None:
            continue
        device_type = dev.get('device_type')
        if not device_type:
            continue
        u_h = device_type.get('u_height')
        if not u_h or u_h <= 0:
            continue
        is_full_depth = device_type.get('is_full_depth', False)

        # Решаем, включать ли устройство в эту сторону
        include = False
        is_opposite = False
        if face == side:
            include = True
        elif is_full_depth:
            # full-depth устройство добавляем на обе стороны
            include = True
            is_opposite = (face != side)  # если face не совпадает с текущей стороной, это противоположная
            if face is None:
                is_opposite = False  # нет чёткой противоположной стороны

        if not include:
            continue

        side_devices.append({
            'name': name,
            'position': position,
            'height_u': u_h,
            'is_full_depth': is_full_depth,
            'is_opposite_side': is_opposite,
            'device_type': device_type,
            'serial': dev.get('serial')
        })
    side_devices.sort(key=lambda x: x['position'])
    if debug:
        print(f"Сторона {side}: найдено {len(side_devices)} устройств (включая full-depth)")
    return side_devices

def generate_rack_view(root, rack_name, u_height, devices, desc_units,
                       offset_x, offset_y, side_label, fill_color):
    """
    Генерирует одну стойку (front или rear) в указанных координатах.
    """
    unit_width = 200
    unit_height_px = 50

    # Рамка стойки (без изменений)
    rack_width = unit_width
    rack_height = u_height * unit_height_px
    frame_id = f"frame_{side_label}"
    frame = ET.SubElement(root, 'mxCell', id=frame_id, value="",
                          style="rounded=0;whiteSpace=wrap;html=1;strokeColor=#000000;fillColor=none;",
                          vertex="1", parent="1")
    ET.SubElement(frame, 'mxGeometry', attrib={
        'x': str(offset_x), 'y': str(offset_y),
        'width': str(rack_width), 'height': str(rack_height),
        'as': 'geometry'
    })

    # Заголовок (без изменений)
    title_id = f"title_{side_label}"
    title = ET.SubElement(root, 'mxCell', id=title_id, value=f"{rack_name} – {side_label.capitalize()}",
                          style="text;html=1;strokeColor=none;fillColor=none;align=center;verticalAlign=middle;whiteSpace=wrap;rounded=0;fontSize=14;fontStyle=1;",
                          vertex="1", parent="1")
    ET.SubElement(title, 'mxGeometry', attrib={
        'x': str(offset_x + rack_width/2), 'y': str(offset_y - 25),
        'width': "200", 'height': "30",
        'as': 'geometry'
    })

    # Подписи юнитов (без изменений)
    label_style = "text;html=1;strokeColor=none;fillColor=none;align=center;verticalAlign=middle;whiteSpace=wrap;rounded=0;fontSize=10;fontColor=#666666;"
    for i in range(1, u_height + 1):
        if desc_units:
            y = offset_y + (i - 1) * unit_height_px
        else:
            y = offset_y + (u_height - i) * unit_height_px
        label = ET.SubElement(root, 'mxCell', id=f"unit_label_{side_label}_{i}", value=str(i),
                              style=label_style, vertex="1", parent="1")
        ET.SubElement(label, 'mxGeometry', attrib={
            'x': str(offset_x - 25), 'y': str(y),
            'width': "20", 'height': str(unit_height_px),
            'as': 'geometry'
        })

    # Устройства
    next_id = 2
    for dev in devices:
        position = dev['position']
        height_u = dev['height_u']
        is_opposite = dev.get('is_opposite_side', False)
        name = html_escape(dev.get('name') or "")
        device_type_obj = dev.get('device_type')
        manufacturer = html_escape(device_type_obj.get('manufacturer', {}).get('name', ''))
        model = html_escape(device_type_obj.get('model', ''))
        if manufacturer and model:
            device_type_str = f"{manufacturer} {model}"
        elif model:
            device_type_str = model
        elif manufacturer:
            device_type_str = manufacturer
        else:
            device_type_str = ""
        serial = html_escape(dev.get('serial', ''))
        serial_str = f"SN: {serial}" if serial else ""

        parts = [name]
        if device_type_str:
            parts.append(device_type_str)
        if serial_str:
            parts.append(serial_str)
        value = "<br/>".join(parts)

        # Базовый стиль
        style = f"rounded=0;whiteSpace=wrap;html=1;fillColor={fill_color};strokeColor=#6c8ebf;fontColor=#1e1e1e;fontSize=12;align=center;verticalAlign=middle;"
        if is_opposite:
            # Для противоположной стороны добавляем штриховку
            style += "fillStyle=hatch;hatchColor=#000000;"
        # Если не opposite, оставляем сплошную заливку

        if desc_units:
            y = offset_y + (position - 1) * unit_height_px
        else:
            y = offset_y + (u_height - position - (height_u - 1)) * unit_height_px

        cell = ET.SubElement(root, 'mxCell', id=f"device_{side_label}_{next_id}", value=value,
                             style=style, vertex="1", parent="1")
        ET.SubElement(cell, 'mxGeometry', attrib={
            'x': str(offset_x), 'y': str(y),
            'width': str(unit_width), 'height': str(height_u * unit_height_px),
            'as': 'geometry'
        })
        next_id += 1

def generate_drawio(rack_name, u_height, side_data, desc_units, both_views):
    mxfile = ET.Element('mxfile', host="app.diagrams.net", modified="2024-01-01T00:00:00.000Z",
                        agent="Python NetBox to Draw.io", version="21.0.0")
    diagram = ET.SubElement(mxfile, 'diagram', id="rack-diagram", name="Page-1")
    model = ET.SubElement(diagram, 'mxGraphModel', dx="1422", dy="794", grid="1",
                          gridSize="10", guides="1", tooltips="1", connect="1",
                          arrows="1", fold="1", page="1", pageScale="1",
                          pageWidth="1169", pageHeight="827", math="0", shadow="0")
    root = ET.SubElement(model, 'root')

    ET.SubElement(root, 'mxCell', id="0")
    ET.SubElement(root, 'mxCell', id="1", parent="0")

    if both_views:
        # Левая стойка – front
        generate_rack_view(root, rack_name, u_height, side_data['front'], desc_units,
                           offset_x=50, offset_y=50, side_label='front', fill_color='#d0e0f0')
        # Правая стойка – rear
        generate_rack_view(root, rack_name, u_height, side_data['rear'], desc_units,
                           offset_x=300, offset_y=50, side_label='rear', fill_color='#f0e0d0')
    else:
        # Одиночный вид
        side = side_data['side']
        fill_color = '#d0e0f0' if side == 'front' else '#f0e0d0'
        generate_rack_view(root, rack_name, u_height, side_data['devices'], desc_units,
                           offset_x=50, offset_y=50, side_label=side, fill_color=fill_color)

    return mxfile

def prettify(elem):
    rough = ET.tostring(elem, 'utf-8')
    reparsed = minidom.parseString(rough)
    return reparsed.toprettyxml(indent="  ")

def main():
    parser = argparse.ArgumentParser(description="Визуализация стойки NetBox в draw.io")
    parser.add_argument("rack_url", help="URL стойки (например, https://netbox/api/dcim/racks/1/)")
    parser.add_argument("token", help="API токен")
    parser.add_argument("--side", choices=['front', 'rear'], default='front',
                        help="Сторона для отображения (используется, если не указан --both-views)")
    parser.add_argument("--both-views", action="store_true",
                        help="Отображать front и rear view одновременно")
    parser.add_argument("--output", "-o", default="rack_diagram.drawio")
    parser.add_argument("--no-verify", action="store_true", help="Отключить проверку SSL")
    parser.add_argument("--ca-bundle", help="Путь к CA-сертификату")
    parser.add_argument("--debug", action="store_true", help="Подробный вывод")
    parser.add_argument("--unit-height", type=int, default=50, help="Высота одного юнита в пикселях")
    args = parser.parse_args()

    if "/api/" not in args.rack_url:
        print("Предупреждение: в URL отсутствует '/api/'.", file=sys.stderr)

    session = requests.Session()
    session.headers.update({"Authorization": f"Token {args.token}", "Accept": "application/json"})

    if args.no_verify:
        session.verify = False
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        print("Предупреждение: проверка SSL отключена!", file=sys.stderr)
    elif args.ca_bundle:
        session.verify = args.ca_bundle

    try:
        rack_data = fetch_rack_data(session, args.rack_url)
        rack_id = rack_data['id']
        rack_name = rack_data.get('name', f"Стойка {rack_id}")
        u_height = rack_data.get('u_height', 42)
        desc_units = rack_data.get('desc_units', False)

        base_match = re.match(r'(https?://[^/]+)', rack_data['url'])
        if not base_match:
            raise ValueError("Не удалось определить базовый URL NetBox")
        base_url = base_match.group(1)

        devices = fetch_devices_in_rack(session, rack_id, base_url)

        if args.debug:
            print(f"Получено устройств: {len(devices)}")

        enrich_device_types(session, devices, base_url, debug=args.debug)

        if args.both_views:
            front_devices = build_side_data(devices, u_height, 'front', desc_units, args.debug)
            rear_devices = build_side_data(devices, u_height, 'rear', desc_units, args.debug)
            side_data = {'front': front_devices, 'rear': rear_devices}
        else:
            side = args.side
            side_devices = build_side_data(devices, u_height, side, desc_units, args.debug)
            side_data = {'side': side, 'devices': side_devices}

        mxfile = generate_drawio(rack_name, u_height, side_data, desc_units, args.both_views)

        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(prettify(mxfile))

        print(f"Диаграмма сохранена в {args.output}")

    except Exception as e:
        print(f"Ошибка: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()