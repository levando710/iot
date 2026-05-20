from __future__ import annotations

import argparse
import os
import re
import sqlite3
import time
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

try:
    import easyocr
except Exception as error:  # pragma: no cover
    easyocr = None
    EASYOCR_IMPORT_ERROR = error
else:
    EASYOCR_IMPORT_ERROR = None

try:
    from deepface import DeepFace
except Exception as error:  # pragma: no cover
    DeepFace = None
    DEEPFACE_IMPORT_ERROR = error
else:
    DEEPFACE_IMPORT_ERROR = None

try:
    from ultralytics import YOLO
except Exception as error:  # pragma: no cover
    YOLO = None
    YOLO_IMPORT_ERROR = error
else:
    YOLO_IMPORT_ERROR = None


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env", override=True)

DB_PATH = BASE_DIR / "quan_ly_ktx.db"
FACE_DB_DIR = BASE_DIR / "database_khuonmat"
DEBUG_DIR = BASE_DIR / "debug_camera"
OUTPUT_DIR = BASE_DIR / "test_outputs"
YOLO_MODEL_PATH = os.getenv("YOLO_MODEL_PATH", "best.pt")

console = Console()


def normalize_plate(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", text or "").upper()


def get_student(student_id: str) -> Optional[dict]:
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT id_sinhvien, ho_ten, duong_dan_anh FROM SinhVien WHERE id_sinhvien = ?",
            (student_id,),
        ).fetchone()
        return dict(row) if row else None


def get_vehicle(plate: str) -> Optional[dict]:
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT bien_so, id_sinhvien, trang_thai FROM PhuongTien WHERE bien_so = ?",
            (plate,),
        ).fetchone()
        return dict(row) if row else None


def resolve_student_id_from_identity(identity_path: str) -> str:
    stem = Path(identity_path).stem
    student = get_student(stem)
    return student["id_sinhvien"] if student else stem


def print_header(title: str, subtitle: str) -> None:
    console.rule(f"[bold cyan]{title}")
    console.print(Panel(subtitle, border_style="cyan"))


def ensure_dependencies(mode: str) -> None:
    missing = []
    if mode in {"face", "all"} and DeepFace is None:
        missing.append(f"DeepFace: {DEEPFACE_IMPORT_ERROR}")
    if mode in {"plate", "all"} and YOLO is None:
        missing.append(f"Ultralytics YOLO: {YOLO_IMPORT_ERROR}")
    if mode in {"plate", "all"} and easyocr is None:
        missing.append(f"EasyOCR: {EASYOCR_IMPORT_ERROR}")
    if missing:
        raise RuntimeError("Thieu thu vien:\n- " + "\n- ".join(missing))


def annotate_face(image_path: Path, output_path: Path, success: bool, label: str) -> None:
    img = cv2.imread(str(image_path))
    if img is None:
        return
    h, w = img.shape[:2]
    color = (28, 128, 42) if success else (28, 28, 185)
    x1, y1 = int(w * 0.25), int(h * 0.12)
    x2, y2 = int(w * 0.75), int(h * 0.88)
    cv2.rectangle(img, (x1, y1), (x2, y2), color, 4)
    cv2.rectangle(img, (x1, max(0, y1 - 42)), (min(w - 1, x1 + 520), y1), color, -1)
    cv2.putText(
        img,
        label,
        (x1 + 12, max(28, y1 - 12)),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )
    cv2.imwrite(str(output_path), img)


def run_face_test(image_path: Path) -> bool:
    print_header(
        "HINH 13 - TEST NHAN DIEN KHUON MAT",
        f"Anh dau vao: {image_path}\nThu muc anh mau: {FACE_DB_DIR}",
    )
    start = time.perf_counter()
    identity = None
    error_message = ""

    try:
        results = DeepFace.find(
            img_path=str(image_path),
            db_path=str(FACE_DB_DIR),
            model_name="Facenet",
            detector_backend="opencv",
            enforce_detection=False,
            silent=True,
        )
        for df in results:
            if df is not None and not df.empty:
                identity = str(df.iloc[0].get("identity", ""))
                break
    except Exception as error:
        error_message = str(error)

    elapsed_ms = (time.perf_counter() - start) * 1000
    student_id = resolve_student_id_from_identity(identity) if identity else None
    student = get_student(student_id) if student_id else None
    success = bool(student)

    table = Table(title="Ket qua DeepFace")
    table.add_column("Hang muc", style="bold")
    table.add_column("Gia tri")
    table.add_row("Trang thai", "[green]THANH CONG[/green]" if success else "[red]THAT BAI[/red]")
    table.add_row("Identity path", identity or "-")
    table.add_row("ID sinh vien", student_id or "-")
    table.add_row("Ho ten", student["ho_ten"] if student else "-")
    table.add_row("Thoi gian xu ly", f"{elapsed_ms:.0f} ms")
    table.add_row("Log su kien", "KTX_ACCESS_GRANTED" if success else "KTX_ACCESS_DENIED")
    if error_message:
        table.add_row("Loi", error_message[:160])
    console.print(table)

    OUTPUT_DIR.mkdir(exist_ok=True)
    out = OUTPUT_DIR / ("hinh13_face_success.jpg" if success else "hinh13_face_failed.jpg")
    label = f"MATCH: {student_id}" if success else "UNKNOWN_FACE"
    annotate_face(image_path, out, success, label)
    console.print(f"[bold]Anh ket qua:[/bold] {out}")
    return success


def read_plate_text(reader, img) -> Optional[str]:
    results = reader.readtext(img)
    if not results:
        return None
    raw = "".join(item[1] for item in results if len(item) >= 2)
    normalized = normalize_plate(raw)
    return normalized if len(normalized) >= 6 else None


def annotate_plate(image, boxes, output_path: Path, plate_text: str, success: bool) -> None:
    color = (28, 128, 42) if success else (28, 28, 185)
    for box in boxes:
        x1, y1, x2, y2 = box
        cv2.rectangle(image, (x1, y1), (x2, y2), color, 4)
        cv2.rectangle(image, (x1, max(0, y1 - 40)), (min(image.shape[1] - 1, x1 + 430), y1), color, -1)
        cv2.putText(
            image,
            f"YOLO + OCR: {plate_text or 'NO_PLATE'}",
            (x1 + 10, max(28, y1 - 12)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.75,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )
    cv2.imwrite(str(output_path), image)


def run_plate_test(image_path: Path) -> bool:
    print_header(
        "HINH 14 - TEST YOLO + EASYOCR BIEN SO",
        f"Anh dau vao: {image_path}\nYOLO model: {YOLO_MODEL_PATH}",
    )
    image = cv2.imread(str(image_path))
    if image is None:
        raise RuntimeError(f"Khong doc duoc anh: {image_path}")

    detector = YOLO(YOLO_MODEL_PATH)
    reader = easyocr.Reader(["en"], gpu=False)

    start = time.perf_counter()
    detections = detector.predict(source=image, conf=0.25, verbose=False)
    candidates = []
    boxes = []

    for det in detections:
        if det.boxes is None:
            continue
        for box in det.boxes.xyxy.tolist():
            x1, y1, x2, y2 = [int(v) for v in box]
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(image.shape[1], max(x1 + 1, x2)), min(image.shape[0], max(y1 + 1, y2))
            crop = image[y1:y2, x1:x2]
            text = read_plate_text(reader, crop)
            boxes.append((x1, y1, x2, y2))
            if text:
                candidates.append(text)

    used_fallback = False
    if not candidates:
        used_fallback = True
        text = read_plate_text(reader, image)
        if text:
            candidates.append(text)
        boxes = [(0, 0, image.shape[1] - 1, image.shape[0] - 1)]

    candidates = sorted(set(candidates), key=len, reverse=True)
    plate = candidates[0] if candidates else None
    vehicle = get_vehicle(plate) if plate else None
    elapsed_ms = (time.perf_counter() - start) * 1000
    success = bool(vehicle)

    table = Table(title="Ket qua YOLO + EasyOCR")
    table.add_column("Hang muc", style="bold")
    table.add_column("Gia tri")
    table.add_row("Trang thai", "[green]THANH CONG[/green]" if success else "[red]THAT BAI[/red]")
    table.add_row("So box YOLO", str(len(boxes)))
    table.add_row("Fallback OCR toan frame", "Co" if used_fallback else "Khong")
    table.add_row("Cac candidate OCR", ", ".join(candidates) if candidates else "-")
    table.add_row("Bien so chon", plate or "-")
    table.add_row("SQLite", "Da dang ky" if vehicle else "Khong khop DB")
    table.add_row("Chu xe", vehicle["id_sinhvien"] if vehicle else "-")
    table.add_row("Trang thai xe", vehicle["trang_thai"] if vehicle else "-")
    table.add_row("Thoi gian xu ly", f"{elapsed_ms:.0f} ms")
    table.add_row("Log su kien", "PARKING_ACCESS_GRANTED" if success else f"PARKING_ACCESS_DENIED:{plate or 'NO_PLATE'}")
    console.print(table)

    OUTPUT_DIR.mkdir(exist_ok=True)
    out = OUTPUT_DIR / ("hinh14_plate_success.jpg" if success else "hinh14_plate_failed.jpg")
    annotate_plate(image.copy(), boxes, out, plate or "NO_PLATE", success)
    console.print(f"[bold]Anh ket qua:[/bold] {out}")
    return success


def default_face_image() -> Path:
    for name in ["ktx_in_auth_event.jpg", "parking_out_face_latest.jpg", "ktx_in_latest.jpg"]:
        path = DEBUG_DIR / name
        if path.exists():
            return path
    return FACE_DB_DIR / "B22DCCN214.jpg"


def default_plate_image() -> Path:
    for name in ["parking_out_plate_auth_event.jpg", "parking_in_plate_auth_event.jpg", "parking_in_plate_latest.jpg"]:
        path = DEBUG_DIR / name
        if path.exists():
            return path
    raise FileNotFoundError("Khong tim thay anh bien so trong debug_camera")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Test AI thuc te de chup man hinh bao cao.")
    parser.add_argument(
        "--mode",
        choices=["face", "plate", "all"],
        default="all",
        help="Chon tac vu can test.",
    )
    parser.add_argument("--face-image", default=str(default_face_image()), help="Anh test khuon mat.")
    parser.add_argument("--plate-image", default=str(default_plate_image()), help="Anh test bien so.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    ensure_dependencies(args.mode)

    console.print(Panel.fit("[bold cyan]AI VISUAL TEST FOR REPORT SCREENSHOT[/bold cyan]"))
    console.print(f"Database: {DB_PATH}")
    console.print(f"Output dir: {OUTPUT_DIR}")

    if args.mode in {"face", "all"}:
        run_face_test(Path(args.face_image))
    if args.mode in {"plate", "all"}:
        run_plate_test(Path(args.plate_image))

    console.rule("[bold green]DONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
