import os
# Tắt các thông báo cảnh báo (warning/info) rác của TensorFlow trên Terminal
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2' 

import cv2
from deepface import DeepFace


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMP_IMG_PATH = os.path.join(BASE_DIR, "temp.jpg")


def lay_danh_sach_anh(db_dir):
    dinh_dang_anh = ('.jpg', '.jpeg', '.png', '.bmp', '.webp')
    ds_anh = []
    for thu_muc_goc, _, ds_file in os.walk(db_dir):
        for ten_file in ds_file:
            if ten_file.lower().endswith(dinh_dang_anh):
                ds_anh.append(os.path.join(thu_muc_goc, ten_file))
    return ds_anh


def xoa_file_cache_deepface(db_dir):
    da_xoa = False
    for ten_file in os.listdir(db_dir):
        if ten_file.lower().endswith('.pkl') and ten_file.startswith('ds_model_'):
            duong_dan = os.path.join(db_dir, ten_file)
            try:
                os.remove(duong_dan)
                da_xoa = True
                print(f"[AI] Đã xóa cache DeepFace: {ten_file}")
            except Exception as loi_xoa:
                print(f"[AI] Không thể xóa cache {ten_file}: {loi_xoa}")
    return da_xoa


def kiem_tra_anh_mau_co_mat(ds_anh_mau):
    ds_hop_le = []
    ds_khong_hop_le = []
    for duong_dan_anh in ds_anh_mau:
        try:
            faces = DeepFace.extract_faces(
                img_path=duong_dan_anh,
                detector_backend='opencv',
                enforce_detection=False
            )
            if faces:
                ds_hop_le.append(duong_dan_anh)
            else:
                ds_khong_hop_le.append(duong_dan_anh)
        except Exception:
            ds_khong_hop_le.append(duong_dan_anh)
    return ds_hop_le, ds_khong_hop_le


def tim_nguoi_khop_theo_verify(temp_img_path, ds_anh_hop_le):
    ket_qua_tot_nhat = None

    for duong_dan_anh_mau in ds_anh_hop_le:
        try:
            kq = DeepFace.verify(
                img1_path=temp_img_path,
                img2_path=duong_dan_anh_mau,
                model_name='Facenet',
                detector_backend='opencv',
                enforce_detection=False
            )

            if ket_qua_tot_nhat is None or kq.get("distance", 999) < ket_qua_tot_nhat.get("distance", 999):
                ket_qua_tot_nhat = {
                    "identity": duong_dan_anh_mau,
                    "verified": kq.get("verified", False),
                    "distance": kq.get("distance", 999),
                    "threshold": kq.get("threshold", 0.4)
                }
        except Exception:
            continue

    return ket_qua_tot_nhat

# Mở Webcam máy tính (số 0 thường là webcam mặc định)
cap = cv2.VideoCapture(0)

# Thu muc chua anh mau dung cho DeepFace.
db_path = os.path.join(BASE_DIR, "database_khuonmat")

# Biến lưu trữ kết quả để hiển thị lên màn hình (Mặc định là dòng chữ hướng dẫn)
hien_thi_ten = "San sang! Bam 'c' de quet"
mau_chu = (255, 255, 0) # Màu xanh lơ (Chuẩn màu BGR của OpenCV)

print("[HỆ THỐNG] Đã mở Camera. Hãy click chuột vào cửa sổ Camera và bấm phím 'C'")

while True:
    ret, frame = cap.read()
    if not ret:
        break

    # Vẽ dòng chữ kết quả lên góc trên bên trái của khung hình camera
    # Cú pháp: cv2.putText(ảnh, text, tọa_độ, font_chữ, cỡ_chữ, màu_sắc, độ_dày)
    cv2.putText(frame, hien_thi_ten, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, mau_chu, 2)
    
    # Hiển thị hình ảnh từ webcam
    cv2.imshow("Test AI Nhan Dien", frame)

    # Đọc phím bấm từ bàn phím
    key = cv2.waitKey(1) & 0xFF
    
    # KHI BẤM PHÍM 'c' (chấp nhận cả 'c' thường và 'C' hoa)
    if key == ord('c') or key == ord('C'):
        # Đổi trạng thái hiển thị trên màn hình thành Đang xử lý
        hien_thi_ten = "Dang xu ly..."
        mau_chu = (0, 255, 255) # Đổi chữ sang màu Vàng
        
        # Ép khung hình cập nhật ngay lập tức để người dùng thấy chữ "Đang xử lý"
        cv2.putText(frame, hien_thi_ten, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, mau_chu, 2)
        cv2.imshow("Test AI Nhan Dien", frame)
        cv2.waitKey(1) 
        
        print("\n[AI] Đã nhận lệnh! Đang quét khuôn mặt...")
        try:
            if not os.path.isdir(db_path):
                hien_thi_ten = "Loi: Khong tim thay thu muc mau"
                mau_chu = (0, 0, 255)
                print(f"Lỗi hệ thống: Không tìm thấy thư mục dữ liệu: {db_path}")
                continue

            ds_anh_mau = lay_danh_sach_anh(db_path)
            if not ds_anh_mau:
                hien_thi_ten = "Loi: Chua co anh mau"
                mau_chu = (0, 0, 255)
                print("Lỗi hệ thống: Không có ảnh mẫu trong thư mục database_khuonmat/")
                print("Gợi ý: Thêm ảnh .jpg/.png có khuôn mặt rõ vào database_khuonmat rồi thử lại.")
                continue

            ds_anh_hop_le, ds_anh_loi = kiem_tra_anh_mau_co_mat(ds_anh_mau)
            if not ds_anh_hop_le:
                hien_thi_ten = "Loi: Anh mau khong detect duoc mat"
                mau_chu = (0, 0, 255)
                print("Lỗi hệ thống: Không ảnh mẫu nào detect được khuôn mặt.")
                print("Gợi ý: Chụp ảnh thẳng mặt, đủ sáng, không che mặt.")
                for duong_dan in ds_anh_loi:
                    print(f"- Ảnh lỗi: {os.path.basename(duong_dan)}")
                continue

            # Lưu tạm khung hình hiện tại thành file ảnh để DeepFace đọc
            cv2.imwrite(TEMP_IMG_PATH, frame)

            # Quét ảnh temp.jpg vừa chụp so với thư mục database
            results = None
            da_dung_fallback_verify = False
            for lan_thu in range(2):
                try:
                    results = DeepFace.find(img_path=TEMP_IMG_PATH,
                                            db_path=db_path,
                                            model_name='Facenet',
                                            enforce_detection=False)
                    break
                except Exception as loi_find:
                    if "No item found in" in str(loi_find) and lan_thu == 0:
                        print("[AI] DeepFace chưa lấy được dữ liệu mẫu. Đang xóa cache và thử lại...")
                        xoa_file_cache_deepface(db_path)
                        continue
                    if "No item found in" in str(loi_find) and lan_thu == 1:
                        print("[AI] DeepFace.find vẫn lỗi. Chuyển sang chế độ so khớp trực tiếp từng ảnh mẫu...")
                        ket_qua_verify = tim_nguoi_khop_theo_verify(TEMP_IMG_PATH, ds_anh_hop_le)
                        if ket_qua_verify:
                            da_dung_fallback_verify = True
                            results = [{
                                "identity": [ket_qua_verify["identity"]],
                                "distance": [ket_qua_verify["distance"]],
                                "threshold": [ket_qua_verify["threshold"]],
                                "verified": [ket_qua_verify["verified"]]
                            }]
                            break
                    raise
            
            # Nếu danh sách kết quả trả về có dữ liệu (tìm thấy người khớp)
            if results is not None and len(results[0]) > 0:
                nguoi_khop = results[0]['identity'][0]
                la_khop = True
                if da_dung_fallback_verify:
                    la_khop = bool(results[0].get('verified', [False])[0])
                
                # Cắt lấy tên file (Ví dụ đường dẫn là database_khuonmat/Tuan.jpg -> Cắt lấy chữ 'Tuan')
                ten = os.path.basename(nguoi_khop).split('.')[0]

                if la_khop:
                    hien_thi_ten = f"XAC NHAN: {ten} - MO CUA!"
                    mau_chu = (0, 255, 0) # Chữ đổi sang màu Xanh lá
                    print(f"✅ {hien_thi_ten}")
                else:
                    hien_thi_ten = "TU CHOI: Nguoi la!"
                    mau_chu = (0, 0, 255)
                    print(f"❌ {hien_thi_ten}")
            else:
                hien_thi_ten = "TU CHOI: Nguoi la!"
                mau_chu = (0, 0, 255) # Chữ đổi sang màu Đỏ
                print(f"❌ {hien_thi_ten}")

            if os.path.exists(TEMP_IMG_PATH):
                os.remove(TEMP_IMG_PATH)
                
        except Exception as e:
            if "No item found in" in str(e):
                hien_thi_ten = "Loi: Du lieu mau chua hop le"
                mau_chu = (0, 0, 255)
                print("Lỗi hệ thống: DeepFace không tìm thấy ảnh mẫu hợp lệ để so khớp.")
                print("Gợi ý: Dùng ảnh mẫu rõ mặt, đủ sáng, mỗi ảnh chỉ 1 người trong database_khuonmat/.")
            else:
                hien_thi_ten = "Loi: Khong thay mat!"
                mau_chu = (0, 0, 255)
                print(f"Lỗi hệ thống: {e}")
            if os.path.exists(TEMP_IMG_PATH):
                os.remove(TEMP_IMG_PATH)

    # Bấm phím 'q' hoặc 'Q' để thoát chương trình
    elif key == ord('q') or key == ord('Q'):
        print("[HỆ THỐNG] Đang tắt Camera...")
        break

# Giải phóng Camera và đóng tất cả cửa sổ
cap.release()
cv2.destroyAllWindows()
