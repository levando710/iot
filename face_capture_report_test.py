from __future__ import annotations

import argparse
import os
import sqlite3
import time
from pathlib import Path
from typing import Optional

import cv2
from dotenv import load_dotenv

try:
    from deepface import DeepFace
except Exception as error:  # pragma: no cover
    DeepFace = None
    DEEPFACE_IMPORT_ERROR = error
else:
    DEEPFACE_IMPORT_ERROR = None


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env", override=True)

DB_PATH = BASE_DIR / "quan_ly_ktx.db"
FACE_DB_DIR = BASE_DIR / "database_khuonmat"
OUTPUT_DIR = BASE_DIR / "test_outputs"


def read_int_env(key: str, default: int = 0) -> int:
    raw = os.getenv(key, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def default_camera_source() -> object:
    url = os.getenv("CAMERA_KTX_IN_URL", "").strip() or os.getenv("CAMERA_URL", "").strip()
    if url:
        return url
    return read_int_env("CAMERA_KTX_IN_INDEX", read_int_env("CAMERA_INDEX", 0))


def open_capture(source: object) -> cv2.VideoCapture:
    if isinstance(source, int) and os.name == "nt":
        return cv2.VideoCapture(source, cv2.CAP_DSHOW)
    if isinstance(source, str):
        return cv2.VideoCapture(source, cv2.CAP_FFMPEG)
    return cv2.VideoCapture(source)


def get_student(student_id: str) -> Optional[dict]:
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT id_sinhvien, ho_ten, duong_dan_anh FROM SinhVien WHERE id_sinhvien = ?",
            (student_id,),
        ).fetchone()
        return dict(row) if row else None


def resolve_student_id(identity_path: str) -> str:
    return Path(identity_path).stem


def run_deepface(frame_path: Path) -> tuple[bool, str, str]:
    if DeepFace is None:
        return False, "DEEPFACE_NOT_AVAILABLE", str(DEEPFACE_IMPORT_ERROR)

    try:
        results = DeepFace.find(
            img_path=str(frame_path),
            db_path=str(FACE_DB_DIR),
            model_name="Facenet",
            detector_backend="opencv",
            enforce_detection=False,
            silent=True,
        )
    except Exception as error:
        return False, "DEEPFACE_ERROR", str(error)

    identity = ""
    for df in results:
        if df is not None and not df.empty:
            identity = str(df.iloc[0].get("identity", ""))
            break

    if not identity:
        return False, "UNKNOWN_FACE", "Khong tim thay khuon mat khop anh mau"

    student_id = resolve_student_id(identity)
    student = get_student(student_id)
    if not student:
        return False, f"NOT_IN_DB:{student_id}", identity

    return True, student["id_sinhvien"], student["ho_ten"]


def draw_status(frame, faces, message: str, color: tuple[int, int, int]) -> None:
    for (x, y, w, h) in faces:
        cv2.rectangle(frame, (x, y), (x + w, y + h), color, 3)
        cv2.putText(
            frame,
            "FACE",
            (x, max(30, y - 10)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            color,
            2,
            cv2.LINE_AA,
        )

    overlay_h = 92
    cv2.rectangle(frame, (0, 0), (frame.shape[1], overlay_h), (17, 24, 39), -1)
    cv2.putText(
        frame,
        "FACE CAPTURE TEST - KTX",
        (18, 34),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.9,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )
    cv2.putText(
        frame,
        message,
        (18, 70),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.72,
        color,
        2,
        cv2.LINE_AA,
    )


def save_result(frame, raw_frame, faces, mode_label: str, success: bool, identity: str, detail: str) -> Path:
    OUTPUT_DIR.mkdir(exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    raw_path = OUTPUT_DIR / f"face_capture_raw_{timestamp}.jpg"
    result_path = OUTPUT_DIR / f"hinh13_face_capture_{mode_label}_{timestamp}.jpg"

    cv2.imwrite(str(raw_path), raw_frame)

    color = (40, 167, 69) if success else (40, 40, 220)
    status = "KTX_ACCESS_GRANTED" if success else "KTX_ACCESS_DENIED"
    label = f"{status} | {identity}"

    annotated = frame.copy()
    draw_status(annotated, faces, label, color)

    y0 = annotated.shape[0] - 82
    cv2.rectangle(annotated, (0, y0), (annotated.shape[1], annotated.shape[0]), (255, 255, 255), -1)
    cv2.putText(
        annotated,
        f"Raw frame saved: {raw_path.name}",
        (18, y0 + 30),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.65,
        (31, 41, 55),
        2,
        cv2.LINE_AA,
    )
    cv2.putText(
        annotated,
        f"Detail: {detail[:90]}",
        (18, y0 + 62),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.65,
        (31, 41, 55),
        2,
        cv2.LINE_AA,
    )

    cv2.imwrite(str(result_path), annotated)
    return result_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Mo camera, chup khuon mat va test DeepFace de dua vao bao cao.")
    parser.add_argument("--camera-url", default="", help="URL camera IP Webcam, vi du http://ip:8080/video")
    parser.add_argument("--camera-index", type=int, default=None, help="Index webcam local, vi du 0")
    parser.add_argument("--width", type=int, default=1280, help="Chieu rong frame hien thi")
    parser.add_argument("--height", type=int, default=720, help="Chieu cao frame hien thi")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.camera_url:
        source: object = args.camera_url
    elif args.camera_index is not None:
        source = args.camera_index
    else:
        source = default_camera_source()

    cap = open_capture(source)
    if not cap.isOpened():
        print(f"[LOI] Khong mo duoc camera: {source}")
        return 1

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)

    cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    face_detector = cv2.CascadeClassifier(cascade_path)
    if face_detector.empty():
        print(f"[LOI] Khong load duoc Haar cascade: {cascade_path}")
        return 1

    print("[OK] Face capture test dang chay.")
    print(f"[INFO] Camera source: {source}")
    print("[PHIM] SPACE: chup + test DeepFace | S: luu anh minh hoa | Q: thoat")

    window_name = "Hinh 13 - Face Capture Test"
    last_message = "Dua mat vao khung hinh. SPACE de chup va test DeepFace."
    last_color = (59, 130, 246)

    while True:
        ok, frame = cap.read()
        if not ok or frame is None:
            print("[WARN] Khong doc duoc frame camera.")
            time.sleep(0.2)
            continue

        raw_frame = frame.copy()
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = face_detector.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(80, 80))

        live = frame.copy()
        message = last_message
        color = last_color
        if len(faces) > 0:
            message = f"Da phat hien {len(faces)} khuon mat. SPACE de chup."
            color = (40, 167, 69)
        draw_status(live, faces, message, color)

        cv2.imshow(window_name, live)
        key = cv2.waitKey(1) & 0xFF

        if key in (ord("q"), ord("Q"), 27):
            break

        if key in (ord("s"), ord("S")):
            out = save_result(live, raw_frame, faces, "manual", True, "CAPTURED_FRAME", "Anh minh hoa frame camera dang chup khuon mat")
            print(f"[OK] Da luu anh minh hoa: {out}")
            last_message = f"Da luu anh minh hoa: {out.name}"
            last_color = (40, 167, 69)

        if key == 32:
            OUTPUT_DIR.mkdir(exist_ok=True)
            temp_path = OUTPUT_DIR / "face_capture_temp.jpg"
            cv2.imwrite(str(temp_path), raw_frame)
            print("[INFO] Dang chay DeepFace...")
            success, identity, detail = run_deepface(temp_path)
            out = save_result(live, raw_frame, faces, "success" if success else "failed", success, identity, detail)
            print("[KET QUA]", "THANH CONG" if success else "THAT BAI", "|", identity, "|", detail)
            print(f"[OK] Da luu anh ket qua: {out}")
            last_message = ("Thanh cong: " if success else "That bai: ") + identity
            last_color = (40, 167, 69) if success else (40, 40, 220)

    cap.release()
    cv2.destroyAllWindows()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
