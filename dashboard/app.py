from __future__ import annotations

import os
import re
import sqlite3
from pathlib import Path
from typing import Optional

from flask import Flask, flash, g, redirect, render_template, request, url_for
from werkzeug.datastructures import FileStorage

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DB_PATH = os.path.join(BASE_DIR, "quan_ly_ktx.db")
FACE_DATASET_DIR = os.path.join(BASE_DIR, "database_khuonmat")

STATUS_OPTIONS = ["Ngoai_Bai", "Trong_Bai"]
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def create_app(db_path: Optional[str] = None) -> Flask:
    app = Flask(
        __name__,
        template_folder=os.path.join(os.path.dirname(__file__), "templates"),
        static_folder=os.path.join(os.path.dirname(__file__), "static"),
    )
    app.config["DATABASE"] = db_path or os.getenv("DASHBOARD_DB_PATH", DEFAULT_DB_PATH)
    app.config["SECRET_KEY"] = os.getenv("DASHBOARD_SECRET_KEY", "ktx-dashboard-dev-secret")
    app.config["FACE_DATASET_DIR"] = os.getenv("FACE_DATASET_DIR", FACE_DATASET_DIR)
    os.makedirs(app.config["FACE_DATASET_DIR"], exist_ok=True)

    def get_db() -> sqlite3.Connection:
        if "db" not in g:
            conn = sqlite3.connect(app.config["DATABASE"])
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            g.db = conn
        return g.db

    @app.teardown_appcontext
    def close_db(_error):
        conn = g.pop("db", None)
        if conn is not None:
            conn.close()

    def normalize_plate(plate: str) -> str:
        return "".join(ch for ch in plate.upper().strip() if ch.isalnum())

    def normalize_student_id(student_id: str) -> str:
        return re.sub(r"[^A-Za-z0-9_-]", "", student_id.strip())

    def _guess_image_extension(file_storage: FileStorage) -> Optional[str]:
        raw_name = file_storage.filename or ""
        ext = Path(raw_name).suffix.lower()
        if ext in ALLOWED_EXTENSIONS:
            return ".jpg" if ext == ".jpeg" else ext
        content_type = (file_storage.content_type or "").lower()
        if content_type.endswith("jpeg"):
            return ".jpg"
        if content_type.endswith("png"):
            return ".png"
        if content_type.endswith("bmp"):
            return ".bmp"
        if content_type.endswith("webp"):
            return ".webp"
        return None

    def save_student_image(student_id: str, file_storage: FileStorage) -> str:
        ext = _guess_image_extension(file_storage)
        if not ext:
            raise ValueError("Ảnh không hợp lệ. Chỉ chấp nhận .jpg/.jpeg/.png/.bmp/.webp")
        normalized_id = normalize_student_id(student_id)
        if not normalized_id:
            raise ValueError("MSV không hợp lệ để đặt tên file ảnh")
        target_name = f"{normalized_id}{ext}"
        target_path = os.path.join(app.config["FACE_DATASET_DIR"], target_name)
        file_storage.save(target_path)
        return target_name

    def clear_deepface_cache() -> None:
        dataset_dir = app.config["FACE_DATASET_DIR"]
        try:
            for file_name in os.listdir(dataset_dir):
                if file_name.startswith("ds_model_") and file_name.endswith(".pkl"):
                    os.remove(os.path.join(dataset_dir, file_name))
        except OSError:
            pass

    @app.get("/")
    def root():
        return redirect(url_for("dashboard"))

    @app.get("/dashboard")
    def dashboard():
        db = get_db()
        students = db.execute("SELECT COUNT(*) FROM SinhVien").fetchone()[0]
        vehicles = db.execute("SELECT COUNT(*) FROM PhuongTien").fetchone()[0]
        in_parking = db.execute("SELECT COUNT(*) FROM PhuongTien WHERE trang_thai = 'Trong_Bai'").fetchone()[0]
        recent_logs = db.execute(
            "SELECT id_log, thoi_gian, su_kien, doi_tuong FROM LichSu ORDER BY id_log DESC LIMIT 10"
        ).fetchall()
        return render_template(
            "dashboard.html",
            stats={
                "students": students,
                "vehicles": vehicles,
                "in_parking": in_parking,
                "recent_logs": recent_logs,
            },
        )

    @app.get("/students")
    def students_page():
        db = get_db()
        students = db.execute(
            """
            SELECT sv.id_sinhvien, sv.ho_ten, sv.duong_dan_anh, COUNT(pt.bien_so) AS so_xe
            FROM SinhVien sv
            LEFT JOIN PhuongTien pt ON pt.id_sinhvien = sv.id_sinhvien
            GROUP BY sv.id_sinhvien, sv.ho_ten, sv.duong_dan_anh
            ORDER BY sv.id_sinhvien ASC
            """
        ).fetchall()
        return render_template("students.html", students=students)

    @app.post("/students")
    def students_create():
        student_id = request.form.get("id_sinhvien", "").strip()
        ho_ten = request.form.get("ho_ten", "").strip()
        face_image = request.files.get("face_image")
        if not student_id or not ho_ten:
            flash("Thiếu dữ liệu. Cần id_sinhvien và ho_ten.", "error")
            return redirect(url_for("students_page"))
        if face_image is None or not face_image.filename:
            flash("Vui lòng upload ảnh khuôn mặt cho sinh viên.", "error")
            return redirect(url_for("students_page"))
        normalized_id = normalize_student_id(student_id)
        if not normalized_id:
            flash("MSV chỉ nên gồm chữ, số, '_' hoặc '-'.", "error")
            return redirect(url_for("students_page"))
        if normalized_id != student_id:
            flash(f"MSV đã được chuẩn hóa từ '{student_id}' thành '{normalized_id}'.", "success")
        try:
            duong_dan_anh = save_student_image(normalized_id, face_image)
        except ValueError as error:
            flash(str(error), "error")
            return redirect(url_for("students_page"))
        db = get_db()
        try:
            db.execute(
                "INSERT INTO SinhVien (id_sinhvien, ho_ten, duong_dan_anh) VALUES (?, ?, ?)",
                (normalized_id, ho_ten, duong_dan_anh),
            )
            db.commit()
            clear_deepface_cache()
            flash(f"Đã thêm sinh viên {normalized_id} và lưu ảnh {duong_dan_anh}", "success")
        except sqlite3.IntegrityError as error:
            image_path = os.path.join(app.config["FACE_DATASET_DIR"], duong_dan_anh)
            if os.path.exists(image_path):
                try:
                    os.remove(image_path)
                except OSError:
                    pass
            flash(f"Không thể thêm sinh viên: {error}", "error")
        return redirect(url_for("students_page"))

    @app.get("/students/<student_id>/edit")
    def students_edit_page(student_id: str):
        db = get_db()
        student = db.execute(
            "SELECT id_sinhvien, ho_ten, duong_dan_anh FROM SinhVien WHERE id_sinhvien = ?",
            (student_id,),
        ).fetchone()
        if not student:
            flash(f"Không tìm thấy sinh viên {student_id}", "error")
            return redirect(url_for("students_page"))
        return render_template("student_edit.html", student=student)

    @app.post("/students/<student_id>/edit")
    def students_edit(student_id: str):
        ho_ten = request.form.get("ho_ten", "").strip()
        duong_dan_anh = request.form.get("duong_dan_anh", "").strip()
        face_image = request.files.get("face_image")
        if not ho_ten or not duong_dan_anh:
            flash("Thiếu dữ liệu cập nhật sinh viên.", "error")
            return redirect(url_for("students_edit_page", student_id=student_id))
        if face_image is not None and face_image.filename:
            try:
                duong_dan_anh = save_student_image(student_id, face_image)
            except ValueError as error:
                flash(str(error), "error")
                return redirect(url_for("students_edit_page", student_id=student_id))
        db = get_db()
        try:
            db.execute(
                "UPDATE SinhVien SET ho_ten = ?, duong_dan_anh = ? WHERE id_sinhvien = ?",
                (ho_ten, duong_dan_anh, student_id),
            )
            db.commit()
            if face_image is not None and face_image.filename:
                clear_deepface_cache()
            flash(f"Đã cập nhật sinh viên {student_id}", "success")
        except sqlite3.IntegrityError as error:
            flash(f"Không thể cập nhật sinh viên: {error}", "error")
        return redirect(url_for("students_page"))

    @app.post("/students/<student_id>/delete")
    def students_delete(student_id: str):
        db = get_db()
        vehicle_count = db.execute(
            "SELECT COUNT(*) FROM PhuongTien WHERE id_sinhvien = ?",
            (student_id,),
        ).fetchone()[0]
        if vehicle_count > 0:
            flash(f"Không thể xóa sinh viên {student_id} vì còn {vehicle_count} xe liên kết.", "error")
            return redirect(url_for("students_page"))
            
        student = db.execute("SELECT duong_dan_anh FROM SinhVien WHERE id_sinhvien = ?", (student_id,)).fetchone()
        if student and student["duong_dan_anh"]:
            image_path = os.path.join(app.config["FACE_DATASET_DIR"], student["duong_dan_anh"])
            if os.path.exists(image_path):
                try:
                    os.remove(image_path)
                except OSError:
                    pass
                    
        db.execute("DELETE FROM SinhVien WHERE id_sinhvien = ?", (student_id,))
        db.commit()
        clear_deepface_cache()
        flash(f"Đã xóa sinh viên {student_id}", "success")
        return redirect(url_for("students_page"))

    @app.get("/vehicles")
    def vehicles_page():
        db = get_db()
        vehicles = db.execute(
            "SELECT pt.bien_so, pt.id_sinhvien, sv.ho_ten, pt.trang_thai "
            "FROM PhuongTien pt "
            "LEFT JOIN SinhVien sv ON sv.id_sinhvien = pt.id_sinhvien "
            "ORDER BY pt.bien_so ASC"
        ).fetchall()
        students = db.execute("SELECT id_sinhvien, ho_ten FROM SinhVien ORDER BY id_sinhvien ASC").fetchall()
        return render_template(
            "vehicles.html",
            vehicles=vehicles,
            students=students,
            status_options=STATUS_OPTIONS,
        )

    @app.post("/vehicles")
    def vehicles_create():
        bien_so_raw = request.form.get("bien_so", "")
        bien_so = normalize_plate(bien_so_raw)
        id_sinhvien = request.form.get("id_sinhvien", "").strip()
        trang_thai = request.form.get("trang_thai", "Ngoai_Bai").strip()
        if not bien_so or not id_sinhvien:
            flash("Thiếu dữ liệu. Cần bien_so và id_sinhvien.", "error")
            return redirect(url_for("vehicles_page"))
        if trang_thai not in STATUS_OPTIONS:
            flash("Trạng thái xe không hợp lệ.", "error")
            return redirect(url_for("vehicles_page"))
        db = get_db()
        try:
            db.execute(
                "INSERT INTO PhuongTien (bien_so, id_sinhvien, trang_thai) VALUES (?, ?, ?)",
                (bien_so, id_sinhvien, trang_thai),
            )
            db.commit()
            flash(f"Đã thêm xe {bien_so}", "success")
        except sqlite3.IntegrityError as error:
            flash(f"Không thể thêm xe: {error}", "error")
        return redirect(url_for("vehicles_page"))

    @app.get("/vehicles/<plate>/edit")
    def vehicles_edit_page(plate: str):
        db = get_db()
        vehicle = db.execute(
            "SELECT bien_so, id_sinhvien, trang_thai FROM PhuongTien WHERE bien_so = ?",
            (plate,),
        ).fetchone()
        if not vehicle:
            flash(f"Không tìm thấy xe {plate}", "error")
            return redirect(url_for("vehicles_page"))
        students = db.execute("SELECT id_sinhvien, ho_ten FROM SinhVien ORDER BY id_sinhvien ASC").fetchall()
        return render_template(
            "vehicle_edit.html",
            vehicle=vehicle,
            students=students,
            status_options=STATUS_OPTIONS,
        )

    @app.post("/vehicles/<plate>/edit")
    def vehicles_edit(plate: str):
        id_sinhvien = request.form.get("id_sinhvien", "").strip()
        trang_thai = request.form.get("trang_thai", "Ngoai_Bai").strip()
        if not id_sinhvien or trang_thai not in STATUS_OPTIONS:
            flash("Dữ liệu cập nhật xe không hợp lệ.", "error")
            return redirect(url_for("vehicles_edit_page", plate=plate))
        db = get_db()
        try:
            db.execute(
                "UPDATE PhuongTien SET id_sinhvien = ?, trang_thai = ? WHERE bien_so = ?",
                (id_sinhvien, trang_thai, plate),
            )
            db.commit()
            flash(f"Đã cập nhật xe {plate}", "success")
        except sqlite3.IntegrityError as error:
            flash(f"Không thể cập nhật xe: {error}", "error")
        return redirect(url_for("vehicles_page"))

    @app.post("/vehicles/<plate>/delete")
    def vehicles_delete(plate: str):
        db = get_db()
        db.execute("DELETE FROM PhuongTien WHERE bien_so = ?", (plate,))
        db.commit()
        flash(f"Đã xóa xe {plate}", "success")
        return redirect(url_for("vehicles_page"))

    @app.get("/history")
    def history_page():
        event_filter = request.args.get("event", "").strip()
        keyword = request.args.get("q", "").strip()
        limit = request.args.get("limit", "100").strip()
        try:
            limit_num = max(10, min(int(limit), 1000))
        except ValueError:
            limit_num = 100
        sql = """
            SELECT id_log, thoi_gian, su_kien, doi_tuong
            FROM LichSu
            WHERE 1 = 1
        """
        params: list[str | int] = []
        if event_filter:
            sql += " AND su_kien = ?"
            params.append(event_filter)
        if keyword:
            sql += " AND (doi_tuong LIKE ? OR su_kien LIKE ?)"
            like_kw = f"%{keyword}%"
            params.extend([like_kw, like_kw])
        sql += " ORDER BY id_log DESC LIMIT ?"
        params.append(limit_num)
        db = get_db()
        logs = db.execute(sql, params).fetchall()
        event_options = db.execute("SELECT DISTINCT su_kien FROM LichSu ORDER BY su_kien ASC").fetchall()
        return render_template(
            "history.html",
            logs=logs,
            event_options=event_options,
            selected_event=event_filter,
            keyword=keyword,
            limit=limit_num,
        )

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.getenv("DASHBOARD_PORT", "5001")), debug=False)
