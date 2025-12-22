# Telegram Attendance Bot

Bot Telegram diem danh nhan vien voi xac minh vi tri GPS, chong gian lan, va bao cao Excel.

## Tinh nang

- Dang ky nhan vien voi phe duyet Admin
- Check-in/Check-out bang vi tri GPS
- Xac minh vi tri trong ban kinh van phong (Geofencing)
- Chong gian lan (phat hien vi tri gia, chup man hinh)
- Theo doi di muon
- Bao cao hang ngay va xuat Excel theo thang
- Thong bao broadcast toi tat ca nhan vien

## Cai dat

### 1. Clone va cai dat dependencies

```bash
cd bot_telegram
python -m venv venv
source venv/bin/activate  # Linux/Mac
# hoac: venv\Scripts\activate  # Windows

pip install -r requirements.txt
```

### 2. Cau hinh

Tao file `.env` tu `.env.example`:

```bash
cp .env.example .env
```

Chinh sua `.env`:

```env
# Token tu @BotFather
TELEGRAM_BOT_TOKEN=your_bot_token_here

# Danh sach Telegram user_id cua Admin (phan cach bang dau phay)
ADMIN_USER_IDS=123456789

# Database (mac dinh SQLite)
DATABASE_URL=sqlite:///./attendance.db

# Mui gio
TIMEZONE=Asia/Ho_Chi_Minh

# Gio bat dau lam viec (24h)
WORK_START_HOUR=9
WORK_START_MINUTE=0

# Nguong tinh di muon (phut)
LATE_THRESHOLD_MINUTES=15

# Ban kinh geofence mac dinh (met)
GEOFENCE_DEFAULT_RADIUS=50
```

### 3. Lay User ID cua Admin

1. Nhan tin cho @userinfobot tren Telegram
2. Bot se tra ve User ID cua ban
3. Them ID vao `ADMIN_USER_IDS` trong file `.env`

### 4. Chay bot

```bash
python src/main.py
```

Hoac:

```bash
python -m src.main
```

## Cau truc thu muc

```
bot_telegram/
├── src/
│   ├── main.py              # Entry point
│   ├── config.py            # Cau hinh
│   ├── constants.py         # Hang so va message templates
│   ├── bot/
│   │   ├── __init__.py      # Application factory
│   │   ├── keyboards.py     # Ban phim Telegram
│   │   ├── middlewares.py   # Decorators (require_admin, etc.)
│   │   └── handlers/
│   │       ├── start.py     # Dang ky nguoi dung
│   │       ├── checkin.py   # Check-in/out
│   │       ├── admin.py     # Lenh admin
│   │       ├── location.py  # Thiet lap dia diem
│   │       ├── menu.py      # Xu ly menu
│   │       ├── report.py    # Bao cao
│   │       ├── help.py      # Tro giup
│   │       └── error.py     # Xu ly loi
│   ├── database/
│   │   ├── models.py        # SQLAlchemy models
│   │   └── session.py       # Database session
│   └── services/
│       ├── user_service.py  # Quan ly nguoi dung
│       ├── attendance.py    # Diem danh
│       ├── geolocation.py   # Xu ly vi tri
│       ├── anti_cheat.py    # Chong gian lan
│       └── export.py        # Xuat bao cao
├── blueprints/              # Tai lieu thiet ke
├── requirements.txt
├── .env.example
└── README.md
```

## Huong dan su dung

### Danh cho Nhan vien

1. **Dang ky**: Gui `/start` va nhap ho ten
2. **Check-in**: Bam nut "Check-in" va gui vi tri GPS
3. **Check-out**: Bam nut "Check-out" va gui vi tri GPS
4. **Xem trang thai**: Bam "Trang thai" hoac `/status`
5. **Xem lich su**: Bam "Lich su" hoac `/history`

### Danh cho Admin

**Quan ly nguoi dung:**
- `/list_pending` - Xem danh sach cho duyet
- `/approve <user_id>` - Phe duyet nguoi dung
- `/reject <user_id>` - Tu choi nguoi dung
- `/ban <user_id>` - Cam nguoi dung
- `/unban <user_id>` - Bo cam nguoi dung
- `/list_users` - Xem tat ca nguoi dung

**Quan ly dia diem:**
- `/set_location` - Them dia diem van phong moi
- `/list_locations` - Xem danh sach dia diem
- `/delete_location <id>` - Xoa dia diem

**Bao cao:**
- `/today` - Bao cao diem danh hom nay
- `/export_excel [thang] [nam]` - Xuat bao cao Excel
- `/stats` - Thong ke tong hop

**Khac:**
- `/broadcast <tin nhan>` - Gui thong bao toi tat ca
- `/help_admin` - Xem tro giup admin

## Luu y quan trong

1. **Vi tri GPS**: Bot chi chap nhan vi tri truc tiep tu dien thoai, khong chap nhan vi tri chuyen tiep
2. **Thoi gian vi tri**: Vi tri phai duoc gui trong vong 60 giay ke tu khi cap nhat
3. **Ban kinh**: Nguoi dung phai o trong ban kinh cho phep cua van phong de check-in thanh cong
4. **Di muon**: He thong tu dong ghi nhan neu check-in sau gio bat dau + nguong di muon

## Ho tro

Neu gap van de, vui long:
1. Kiem tra file `bot.log` de xem log loi
2. Dam bao `.env` duoc cau hinh dung
3. Dam bao bot token hop le
4. Dam bao Admin user_id dung

## License

MIT License
