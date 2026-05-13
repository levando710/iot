import sqlite3

def setup_database():
    # 1. Tạo file database (nếu file chưa tồn tại, SQLite sẽ tự động tạo file mới)
    # File này sẽ xuất hiện ngay trong thư mục chứa đoạn code này.
    conn = sqlite3.connect('quan_ly_ktx.db')
    cursor = conn.cursor()

    # 2. Tạo bảng Quản lý Sinh Viên
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS SinhVien (
            id_sinhvien TEXT PRIMARY KEY,
            ho_ten TEXT NOT NULL,
            duong_dan_anh TEXT NOT NULL
        )
    ''')

    # 3. Tạo bảng Quản lý Phương Tiện
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS PhuongTien (
            bien_so TEXT PRIMARY KEY,
            id_sinhvien TEXT NOT NULL,
            trang_thai TEXT DEFAULT 'Da_Xuat_Ben',
            FOREIGN KEY (id_sinhvien) REFERENCES SinhVien (id_sinhvien)
        )
    ''')

    # 4. Tạo bảng Nhật ký (Log) Ra/Vào
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS LichSu_RaVao (
            id_log INTEGER PRIMARY KEY AUTOINCREMENT,
            thoi_gian DATETIME DEFAULT CURRENT_TIMESTAMP,
            loai_su_kien TEXT NOT NULL,
            doi_tuong TEXT NOT NULL
        )
    ''')

    # 5. Lưu lại thay đổi và đóng kết nối
    conn.commit()
    conn.close()
    print("[THÀNH CÔNG] Đã khởi tạo file 'quan_ly_ktx.db' và các bảng dữ liệu!")

# Chạy hàm khởi tạo
if __name__ == '__main__':
    setup_database()