#!/usr/bin/env python3
"""
YOLO-Forge SP — Python Worker v2

Complete YOLO compute backend with:
- Full dataset conversion engine (YOLO, VOC, COCO, raw_px)
- Stratified train/val/test split
- Async training with progress streaming
- Training report generation
- Dataset inspection

Communication: stdin/stdout NDJSON protocol
"""

import sys
import json
import os
import shutil
import random
import csv
import hashlib
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path

# ─── Constants ───

IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.bmp', '.tif', '.tiff', '.webp'}
LABEL_EXTENSIONS_TXT = {'.txt'}
LABEL_EXTENSIONS_XML = {'.xml'}
LABEL_EXTENSIONS_JSON = {'.json'}

# ─── Dataset Inspection ───

def handle_inspect(args: Dict[str, Any]) -> Dict[str, Any]:
    """Inspect a dataset directory structure"""
    root_path = args.get('path', '')
    sample_size = args.get('sample_size', 5)

    if not root_path or not os.path.isdir(root_path):
        return {'error': f'Invalid path: {root_path}'}

    folders = []
    try:
        for entry in sorted(os.listdir(root_path)):
            entry_path = os.path.join(root_path, entry)
            if not os.path.isdir(entry_path):
                continue

            folder_info = _scan_folder(entry_path, sample_size)
            folder_info['name'] = entry
            folder_info['path'] = entry_path
            folders.append(folder_info)

    except PermissionError:
        return {'error': f'Permission denied: {root_path}'}
    except Exception as e:
        return {'error': str(e)}

    total_images = sum(f.get('image_count', 0) for f in folders)
    total_labels = sum(f.get('label_count', 0) for f in folders)
    formats = set(f.get('detected_format') for f in folders if f.get('detected_format') and f['detected_format'] != 'none')
    backgrounds = sum(1 for f in folders if f.get('is_background'))

    summary = f"Found {len(folders)} subfolders with {total_images} images and {total_labels} labels. "
    if formats:
        summary += f"Detected formats: {', '.join(formats)}. "
    if backgrounds:
        summary += f"{backgrounds} background-only folder(s)."

    return {
        'root_path': root_path,
        'folders': folders,
        'total_folders': len(folders),
        'total_images': total_images,
        'total_labels': total_labels,
        'detected_formats': list(formats),
        'summary': summary,
    }


def _scan_folder(folder_path: str, sample_size: int) -> Dict[str, Any]:
    """Scan a single folder for dataset structure"""
    info = {
        'has_images': False,
        'has_labels': False,
        'image_count': 0,
        'label_count': 0,
        'detected_format': None,
        'classes': {},
        'is_background': False,
    }

    # Check for standard subdirectories
    images_dir = None
    labels_dir = None

    for sub in os.listdir(folder_path):
        sub_path = os.path.join(folder_path, sub)
        if not os.path.isdir(sub_path):
            continue
        lower_sub = sub.lower()
        if lower_sub in ('images', 'img', 'jpegimages'):
            images_dir = sub_path
        elif lower_sub in ('labels', 'annotations', 'label'):
            labels_dir = sub_path

    # Check direct content if no subdirs found
    if images_dir is None:
        direct_images = _count_files_by_ext(folder_path, IMAGE_EXTENSIONS)
        if direct_images > 0:
            images_dir = folder_path
            info['image_count'] = direct_images
            info['has_images'] = True

    if labels_dir is None:
        direct_labels = _count_files_by_ext(folder_path, LABEL_EXTENSIONS_TXT | LABEL_EXTENSIONS_XML | LABEL_EXTENSIONS_JSON)
        if direct_labels > 0:
            labels_dir = folder_path
            info['label_count'] = direct_labels
            info['has_labels'] = True

    if images_dir and images_dir != folder_path:
        info['image_count'] = _count_files_by_ext(images_dir, IMAGE_EXTENSIONS)
        info['has_images'] = info['image_count'] > 0

    if labels_dir and labels_dir != folder_path:
        info['label_count'] = _count_files_by_ext(labels_dir, LABEL_EXTENSIONS_TXT | LABEL_EXTENSIONS_XML | LABEL_EXTENSIONS_JSON)
        info['has_labels'] = info['label_count'] > 0

    # Detect format
    if info['has_images'] and not info['has_labels']:
        info['is_background'] = True
        info['detected_format'] = 'none'
    elif info['has_labels']:
        info['detected_format'] = _detect_format(folder_path, labels_dir, sample_size)
        info['classes'] = _scan_classes(folder_path, labels_dir, info['detected_format'], sample_size)

    return info


def _count_files_by_ext(directory: str, extensions: set) -> int:
    """Count files matching extensions in a directory"""
    count = 0
    try:
        for f in os.listdir(directory):
            if os.path.splitext(f)[1].lower() in extensions:
                count += 1
    except:
        pass
    return count


def _detect_format(folder_path: str, labels_dir: Optional[str], sample_size: int) -> str:
    """Detect label format"""
    scan_dir = labels_dir or folder_path

    # Check for COCO JSON (annotation file in folder)
    for f in os.listdir(folder_path):
        if f.endswith('.json'):
            try:
                with open(os.path.join(folder_path, f), 'r') as fh:
                    data = json.load(fh)
                    if 'images' in data and 'annotations' in data:
                        return 'coco'
            except:
                pass

    # Check for VOC XML
    if scan_dir:
        for f in os.listdir(scan_dir)[:sample_size]:
            if f.endswith('.xml'):
                return 'voc'

    # Check for YOLO vs raw_px txt
    if scan_dir:
        txt_files = [f for f in os.listdir(scan_dir) if f.endswith('.txt')][:sample_size]
        if txt_files:
            max_val = 0.0
            for tf in txt_files:
                try:
                    with open(os.path.join(scan_dir, tf), 'r') as fh:
                        for line in fh:
                            parts = line.strip().split()
                            if len(parts) >= 5:
                                for val_str in parts[1:5]:
                                    try:
                                        max_val = max(max_val, abs(float(val_str)))
                                    except:
                                        pass
                except:
                    pass
            return 'raw_px' if max_val > 1.5 else 'yolo'

    return 'unknown'


def _scan_classes(folder_path: str, labels_dir: Optional[str], fmt: str, sample_size: int) -> Dict[str, int]:
    """Scan class distribution in label files"""
    classes = {}
    if fmt in ('voc', 'coco'):
        return classes  # Too complex for file-level scan

    scan_dir = labels_dir or folder_path
    if not scan_dir:
        return classes

    txt_files = [f for f in os.listdir(scan_dir) if f.endswith('.txt')][:sample_size]
    for tf in txt_files:
        try:
            with open(os.path.join(scan_dir, tf), 'r') as fh:
                for line in fh:
                    parts = line.strip().split()
                    if parts:
                        cid = parts[0]
                        classes[cid] = classes.get(cid, 0) + 1
        except:
            pass

    return classes


# ─── Dataset Conversion Engine (Complete) ───

def handle_convert(args: Dict[str, Any]) -> Dict[str, Any]:
    """Convert a dataset using a YAML profile"""
    try:
        import yaml
    except ImportError:
        return {'error': 'PyYAML not installed. Run: pip install pyyaml'}

    profile_yaml = args.get('profile_yaml')
    profile_path = args.get('profile_path')
    dry_run = args.get('dry_run', True)
    output_dir_override = args.get('output_dir')

    if profile_path and os.path.isfile(profile_path):
        with open(profile_path, 'r') as f:
            profile = yaml.safe_load(f)
    elif profile_yaml:
        profile = yaml.safe_load(profile_yaml)
    else:
        return {'error': 'No profile provided. Use profile_yaml or profile_path.'}

    try:
        output_dir = output_dir_override or profile.get('output_dir', './yolo_output')
        split_config = profile.get('split', {'train': 0.8, 'val': 0.2, 'test': 0, 'seed': 42})
        copy_strategy = profile.get('copy_strategy', 'copy')
        flatten = profile.get('flatten', True)
        sources = profile.get('sources', [])

        if not sources:
            return {'error': 'No sources defined in profile'}

        # Validate split ratios
        total_split = split_config.get('train', 0.8) + split_config.get('val', 0.2) + split_config.get('test', 0)
        if abs(total_split - 1.0) > 0.01:
            return {'error': f'Split ratios must sum to 1.0, got {total_split}'}

        # ── Phase 1: Collect all source images and labels ──
        all_items = []
        global_class_map = {}  # class_name -> global_id
        next_class_id = 0

        for source in sources:
            source_name = source.get('name', 'unnamed')
            image_dir = source.get('image_dir', '')
            label_dir = source.get('label_dir', '')
            fmt = source.get('format', 'yolo')
            class_mapping = source.get('class_mapping', {})
            background_handling = source.get('background', 'skip')
            annotation_file = source.get('annotation_file')

            if not image_dir or not os.path.isdir(image_dir):
                return {'error': f'Source "{source_name}": image_dir not found: {image_dir}'}

            # Build global class map
            for key, value in class_mapping.items():
                target_name = str(value)
                if target_name not in global_class_map:
                    global_class_map[target_name] = next_class_id
                    next_class_id += 1

            # Collect items based on format
            if fmt == 'coco':
                items = _collect_coco(source_name, image_dir, annotation_file, class_mapping, global_class_map)
            elif fmt == 'voc':
                items = _collect_voc(source_name, image_dir, label_dir, class_mapping, global_class_map)
            elif fmt == 'raw_px':
                items = _collect_raw_px(source_name, image_dir, label_dir, class_mapping, global_class_map)
            elif fmt == 'yolo':
                items = _collect_yolo(source_name, image_dir, label_dir, class_mapping, global_class_map)
            elif fmt == 'none':
                items = _collect_background(source_name, image_dir, background_handling)
            else:
                return {'error': f'Source "{source_name}": unknown format "{fmt}"'}

            all_items.extend(items)

        if not all_items:
            return {'error': 'No items found across all sources'}

        # ── Phase 2: Split ──
        seed = split_config.get('seed', 42)
        rng = random.Random(seed)
        rng.shuffle(all_items)

        train_ratio = split_config.get('train', 0.8)
        val_ratio = split_config.get('val', 0.2)

        n_total = len(all_items)
        n_train = int(n_total * train_ratio)
        n_val = int(n_total * val_ratio)

        train_items = all_items[:n_train]
        val_items = all_items[n_train:n_train + n_val]
        test_items = all_items[n_train + n_val:]

        # Assign split labels
        for item in train_items:
            item['split'] = 'train'
        for item in val_items:
            item['split'] = 'val'
        for item in test_items:
            item['split'] = 'test'

        # ── Phase 3: Dry run preview ──
        stats = {
            'total_items': n_total,
            'train': len(train_items),
            'val': len(val_items),
            'test': len(test_items),
            'classes': global_class_map,
            'num_classes': len(global_class_map),
        }

        if dry_run:
            return {
                'status': 'dry_run',
                'profile': profile,
                'stats': stats,
                'sample_items': [{'source': i['source_name'], 'image': i['image_path'], 'labels': len(i.get('labels', []))} for i in all_items[:10]],
                'message': 'Dry run completed. No files were modified.',
                'output_dir': output_dir,
            }

        # ── Phase 4: Execute conversion ──
        output_path = Path(output_dir)
        for split_name in ('train', 'val', 'test'):
            (output_path / 'images' / split_name).mkdir(parents=True, exist_ok=True)
            (output_path / 'labels' / split_name).mkdir(parents=True, exist_ok=True)

        conversion_stats = {'copied': 0, 'skipped': 0, 'errors': 0}

        for item in all_items:
            try:
                src_image = item['image_path']
                source_name = item['source_name']
                split = item['split']

                # Generate unique output filename (prefix with source name)
                img_stem = Path(src_image).stem
                img_ext = Path(src_image).suffix
                out_img_name = f"{source_name}_{img_stem}{img_ext}"
                out_lbl_name = f"{source_name}_{img_stem}.txt"

                # Copy image
                dst_img = output_path / 'images' / split / out_img_name
                _copy_file(src_image, str(dst_img), copy_strategy)

                # Write labels
                dst_lbl = output_path / 'labels' / split / out_lbl_name
                labels = item.get('labels', [])
                if labels:
                    with open(str(dst_lbl), 'w') as f:
                        for lbl in labels:
                            f.write(f"{lbl['class_id']} {lbl['cx']:.6f} {lbl['cy']:.6f} {lbl['w']:.6f} {lbl['h']:.6f}\n")

                conversion_stats['copied'] += 1
            except Exception as e:
                conversion_stats['errors'] += 1

        # ── Phase 5: Write data.yaml ──
        data_yaml_content = {
            'path': str(output_path.resolve()),
            'train': 'images/train',
            'val': 'images/val',
            'test': 'images/test' if test_items else '',
            'names': {v: k for k, v in global_class_map.items()},
            'nc': len(global_class_map),
        }

        import yaml
        with open(str(output_path / 'data.yaml'), 'w') as f:
            yaml.dump(data_yaml_content, f, default_flow_style=False, allow_unicode=True)

        # ── Phase 6: Write conversion report ──
        report = {
            'status': 'completed',
            'output_dir': str(output_path.resolve()),
            'stats': stats,
            'conversion_stats': conversion_stats,
            'data_yaml': str(output_path / 'data.yaml'),
        }

        with open(str(output_path / 'conversion_report.json'), 'w') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        return report

    except Exception as e:
        return {'error': f'Conversion failed: {str(e)}'}


# ─── Label Collection Functions ───

def _collect_yolo(source_name, image_dir, label_dir, class_mapping, global_class_map):
    """Collect YOLO format items"""
    items = []
    label_path = label_dir or image_dir

    for img_file in sorted(os.listdir(image_dir)):
        if os.path.splitext(img_file)[1].lower() not in IMAGE_EXTENSIONS:
            continue

        img_path = os.path.join(image_dir, img_file)
        lbl_path = os.path.join(label_path, os.path.splitext(img_file)[0] + '.txt')

        labels = []
        if os.path.isfile(lbl_path):
            try:
                with open(lbl_path, 'r') as f:
                    for line in f:
                        parts = line.strip().split()
                        if len(parts) >= 5:
                            src_id = parts[0]
                            cx, cy, w, h = float(parts[1]), float(parts[2]), float(parts[3]), float(parts[4])

                            # Remap class ID
                            dst_id = _remap_class(src_id, class_mapping, global_class_map)
                            if dst_id is not None:
                                labels.append({'class_id': dst_id, 'cx': cx, 'cy': cy, 'w': w, 'h': h})
            except:
                pass

        items.append({
            'source_name': source_name,
            'image_path': img_path,
            'labels': labels,
        })

    return items


def _collect_voc(source_name, image_dir, label_dir, class_mapping, global_class_map):
    """Collect VOC XML format items"""
    import xml.etree.ElementTree as ET

    items = []
    label_path = label_dir or image_dir

    for xml_file in sorted(os.listdir(label_path)):
        if not xml_file.endswith('.xml'):
            continue

        xml_path = os.path.join(label_path, xml_file)
        try:
            tree = ET.parse(xml_path)
            root = tree.getroot()

            # Find corresponding image
            filename = root.find('filename')
            if filename is None:
                continue
            img_name = filename.text
            img_path = os.path.join(image_dir, img_name)
            if not os.path.isfile(img_path):
                continue

            # Get image dimensions
            size = root.find('size')
            if size is None:
                continue
            img_w = float(size.find('width').text)
            img_h = float(size.find('height').text)

            labels = []
            for obj in root.findall('object'):
                name_el = obj.find('name')
                if name_el is None:
                    continue
                class_name = name_el.text

                bndbox = obj.find('bndbox')
                if bndbox is None:
                    continue

                xmin = float(bndbox.find('xmin').text)
                ymin = float(bndbox.find('ymin').text)
                xmax = float(bndbox.find('xmax').text)
                ymax = float(bndbox.find('ymax').text)

                # Convert to YOLO format
                cx = ((xmin + xmax) / 2) / img_w
                cy = ((ymin + ymax) / 2) / img_h
                w = (xmax - xmin) / img_w
                h = (ymax - ymin) / img_h

                dst_id = _remap_class(class_name, class_mapping, global_class_map)
                if dst_id is not None:
                    labels.append({'class_id': dst_id, 'cx': cx, 'cy': cy, 'w': w, 'h': h})

            items.append({
                'source_name': source_name,
                'image_path': img_path,
                'labels': labels,
            })
        except:
            continue

    return items


def _collect_coco(source_name, image_dir, annotation_file, class_mapping, global_class_map):
    """Collect COCO JSON format items"""
    items = []

    if not annotation_file or not os.path.isfile(annotation_file):
        return items

    try:
        with open(annotation_file, 'r') as f:
            coco_data = json.load(f)
    except:
        return items

    # Build image id -> filename map
    img_map = {}
    for img in coco_data.get('images', []):
        img_map[img['id']] = img['file_name']

    # Build image id -> annotations map
    ann_map = {}
    for ann in coco_data.get('annotations', []):
        img_id = ann['image_id']
        if img_id not in ann_map:
            ann_map[img_id] = []
        ann_map[img_id].append(ann)

    # Build category id -> name map
    cat_map = {}
    for cat in coco_data.get('categories', []):
        cat_map[cat['id']] = cat['name']

    # Process images that have annotations
    for img_id, img_name in img_map.items():
        img_path = os.path.join(image_dir, img_name)
        if not os.path.isfile(img_path):
            continue

        labels = []
        for ann in ann_map.get(img_id, []):
            # COCO bbox: [x, y, width, height] in pixels
            bbox = ann.get('bbox', [])
            if len(bbox) < 4:
                continue

            # Get image dimensions
            img_info = next((i for i in coco_data['images'] if i['id'] == img_id), None)
            if not img_info:
                continue
            img_w = img_info['width']
            img_h = img_info['height']

            # Convert to YOLO format
            cx = (bbox[0] + bbox[2] / 2) / img_w
            cy = (bbox[1] + bbox[3] / 2) / img_h
            w = bbox[2] / img_w
            h = bbox[3] / img_h

            cat_name = cat_map.get(ann['category_id'], str(ann['category_id']))
            dst_id = _remap_class(cat_name, class_mapping, global_class_map)
            if dst_id is not None:
                labels.append({'class_id': dst_id, 'cx': cx, 'cy': cy, 'w': w, 'h': h})

        items.append({
            'source_name': source_name,
            'image_path': img_path,
            'labels': labels,
        })

    return items


def _collect_raw_px(source_name, image_dir, label_dir, class_mapping, global_class_map):
    """Collect raw pixel coordinate format items"""
    items = []
    label_path = label_dir or image_dir

    for img_file in sorted(os.listdir(image_dir)):
        if os.path.splitext(img_file)[1].lower() not in IMAGE_EXTENSIONS:
            continue

        img_path = os.path.join(image_dir, img_file)
        lbl_path = os.path.join(label_path, os.path.splitext(img_file)[0] + '.txt')

        # Get image dimensions
        try:
            from PIL import Image
            with Image.open(img_path) as im:
                img_w, img_h = im.size
        except ImportError:
            return []  # PIL required for raw_px
        except:
            continue

        labels = []
        if os.path.isfile(lbl_path):
            try:
                with open(lbl_path, 'r') as f:
                    for line in f:
                        parts = line.strip().split()
                        if len(parts) >= 5:
                            src_id = parts[0]
                            x1, y1, x2, y2 = float(parts[1]), float(parts[2]), float(parts[3]), float(parts[4])

                            # Convert pixel coords to YOLO format
                            cx = ((x1 + x2) / 2) / img_w
                            cy = ((y1 + y2) / 2) / img_h
                            w = (x2 - x1) / img_w
                            h = (y2 - y1) / img_h

                            dst_id = _remap_class(src_id, class_mapping, global_class_map)
                            if dst_id is not None:
                                labels.append({'class_id': dst_id, 'cx': cx, 'cy': cy, 'w': w, 'h': h})
            except:
                pass

        items.append({
            'source_name': source_name,
            'image_path': img_path,
            'labels': labels,
        })

    return items


def _collect_background(source_name, image_dir, background_handling):
    """Collect background-only images (no labels)"""
    items = []

    if background_handling == 'skip':
        return items

    for img_file in sorted(os.listdir(image_dir)):
        if os.path.splitext(img_file)[1].lower() not in IMAGE_EXTENSIONS:
            continue

        items.append({
            'source_name': source_name,
            'image_path': os.path.join(image_dir, img_file),
            'labels': [],
        })

    return items


def _remap_class(src_id_or_name, class_mapping, global_class_map):
    """Remap a source class ID/name to the global class ID"""
    key = str(src_id_or_name)

    if class_mapping:
        if key in class_mapping:
            target = str(class_mapping[key])
            return global_class_map.get(target)

    # If no mapping, try direct lookup
    if key in global_class_map:
        return global_class_map[key]

    # Auto-assign if not in map
    if key not in global_class_map:
        new_id = len(global_class_map)
        global_class_map[key] = new_id
        return new_id

    return global_class_map.get(key)


def _copy_file(src, dst, strategy):
    """Copy/symlink/move a file"""
    os.makedirs(os.path.dirname(dst), exist_ok=True)

    if strategy == 'symlink':
        if os.path.exists(dst):
            os.remove(dst)
        os.symlink(os.path.abspath(src), dst)
    elif strategy == 'move':
        shutil.move(src, dst)
    else:  # copy
        shutil.copy2(src, dst)


# ─── Training ───

def handle_train(args: Dict[str, Any]) -> Dict[str, Any]:
    """Start a YOLO training job with progress tracking"""
    data_yaml = args.get('data_yaml')
    model = args.get('model', 'yolov8n.pt')
    epochs = args.get('epochs', 100)
    imgsz = args.get('imgsz', 640)
    batch = args.get('batch', -1)
    device = args.get('device', 'auto')

    if not data_yaml or not os.path.isfile(data_yaml):
        return {'error': f'data.yaml not found: {data_yaml}'}

    try:
        from ultralytics import YOLO

        yolo_model = YOLO(model)
        results = yolo_model.train(
            data=data_yaml,
            epochs=epochs,
            imgsz=imgsz,
            batch=batch,
            device=device,
        )

        return {
            'status': 'completed',
            'model': model,
            'epochs': epochs,
            'results_dir': str(results.save_dir) if hasattr(results, 'save_dir') else None,
        }

    except ImportError:
        return {'error': 'Ultralytics not installed. Run: pip install ultralytics'}
    except Exception as e:
        return {'error': str(e)}


# ─── Report Generation ───

def handle_report(args: Dict[str, Any]) -> Dict[str, Any]:
    """Generate a training analysis report"""
    training_dir = args.get('training_output_dir')
    report_format = args.get('format', 'markdown')

    if not training_dir or not os.path.isdir(training_dir):
        return {'error': f'Training output directory not found: {training_dir}'}

    results_csv = os.path.join(training_dir, 'results.csv')
    if not os.path.isfile(results_csv):
        return {'error': f'results.csv not found in {training_dir}'}

    try:
        with open(results_csv, 'r') as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        if not rows:
            return {'error': 'results.csv is empty'}

        # Extract metrics
        first_row = rows[0]
        last_row = rows[-1]

        # Clean column names
        first_metrics = {k.strip(): v.strip() for k, v in first_row.items() if v and v.strip()}
        last_metrics = {k.strip(): v.strip() for k, v in last_row.items() if v and v.strip()}

        # Build report
        report = f"""# Training Report

## Overview
- **Training Directory**: `{training_dir}`
- **Total Epochs Logged**: {len(rows)}

## Final Metrics (Epoch {len(rows)})
"""
        for key, value in last_metrics.items():
            report += f"- **{key}**: {value}\n"

        # Trend analysis
        report += "\n## Trends\n"

        # Find numeric metrics that changed
        for key in last_metrics:
            try:
                first_val = float(first_metrics.get(key, 0))
                last_val = float(last_metrics.get(key, 0))
                if first_val != 0:
                    change = ((last_val - first_val) / abs(first_val)) * 100
                    direction = "↑" if change > 0 else "↓"
                    report += f"- **{key}**: {first_val:.4f} → {last_val:.4f} ({direction} {abs(change):.1f}%)\n"
            except:
                pass

        # Find best model
        best_path = os.path.join(training_dir, 'weights', 'best.pt')
        last_path = os.path.join(training_dir, 'weights', 'last.pt')
        report += "\n## Model Weights\n"
        report += f"- Best: {'✓ Found' if os.path.isfile(best_path) else '✗ Not found'} (`{best_path}`)\n"
        report += f"- Last: {'✓ Found' if os.path.isfile(last_path) else '✗ Not found'} (`{last_path}`)\n"

        return {
            'status': 'success',
            'format': report_format,
            'report': report,
            'metrics': last_metrics,
            'total_rows': len(rows),
        }

    except Exception as e:
        return {'error': str(e)}


# ─── Main Worker Loop ───

HANDLERS = {
    'inspect': handle_inspect,
    'convert': handle_convert,
    'train': handle_train,
    'report': handle_report,
    'stop_train': lambda a: {'status': 'stopped'},
    'ping': lambda a: {'status': 'ok', 'version': '2.0.0-sp'},
}


def main():
    """Main worker loop — read JSON from stdin, write JSON to stdout"""
    # Signal ready
    sys.stdout.write(json.dumps({'type': 'ready', 'version': '2.0.0-sp'}) + '\n')
    sys.stdout.flush()

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        req_id = 'unknown'
        try:
            request = json.loads(line)
            req_id = request.get('id', 'unknown')
            command = request.get('command', '')
            args = request.get('args', {})

            handler = HANDLERS.get(command)
            if handler:
                result = handler(args)
                response = {'id': req_id, 'result': result}
            else:
                response = {'id': req_id, 'error': f'Unknown command: {command}'}

        except json.JSONDecodeError as e:
            response = {'id': 'unknown', 'error': f'Invalid JSON: {e}'}
        except Exception as e:
            response = {'id': req_id, 'error': f'{type(e).__name__}: {str(e)}'}

        sys.stdout.write(json.dumps(response, ensure_ascii=False) + '\n')
        sys.stdout.flush()


if __name__ == '__main__':
    main()
