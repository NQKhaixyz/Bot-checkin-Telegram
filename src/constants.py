"""Constants for Telegram Attendance Bot with Point System."""


class Commands:
    """Bot command constants."""
    
    # User commands
    START = "start"
    HELP = "help"
    CHECKIN = "checkin"
    CHECKOUT = "checkout"
    STATUS = "status"  # Gộp status + history
    MINHCHUNG = "minhchung"  # Minh chứng công việc
    
    # Admin commands
    APPROVE = "approve"
    REJECT = "reject"
    BAN = "ban"
    UNBAN = "unban"
    LIST_USERS = "list_users"
    LIST_PENDING = "list_pending"
    SET_MEETING = "set_meeting"  # Thay set_location
    LIST_MEETINGS = "list_meetings"
    TODAY = "today"
    EXPORT = "export"
    BROADCAST = "broadcast"
    RANKING = "ranking"


class CallbackData:
    """Callback data prefixes for inline keyboards."""
    
    CHECKIN = "checkin"
    CHECKOUT = "checkout"
    APPROVE_USER = "approve_user"
    REJECT_USER = "reject_user"
    APPROVE_EVIDENCE = "approve_evidence"
    REJECT_EVIDENCE = "reject_evidence"
    REGISTER_MEETING = "register_meeting"
    CANCEL = "cancel"
    
    @staticmethod
    def make(prefix: str, *args) -> str:
        """Create callback data string from prefix and arguments."""
        if args:
            return f"{prefix}:{':'.join(str(arg) for arg in args)}"
        return prefix
    
    @staticmethod
    def parse(data: str) -> tuple:
        """Parse callback data into prefix and arguments."""
        parts = data.split(":")
        return parts[0], parts[1:] if len(parts) > 1 else []


class Messages:
    """Vietnamese message templates - Gen Z style."""
    
    # Welcome & Registration
    WELCOME = (
        "Yo yo yo! Welcome to CLB nha bestie!\n\n"
        "Chill di, doi admin duyet ti thoi!\n"
        "Ong admin hoi chill nen tu tu nha, dung co gap qua xiu lu"
    )
    WELCOME_BACK = "Ua bro quay lai roi a? Lau qua khong gap, nho ghe luon a!"
    REGISTRATION_PENDING = "Acc dang pending nha! Admin dang touchgrass. Chill xiu di bestie!"
    ALREADY_REGISTERED = "Alo? Dang ky roi con spam chi nua bro?\n\nStatus: {status}\n\nNao ca vang real day!"
    REGISTRATION_APPROVED = "LET'S GOOO! Acc duoc duyet roi nha!\n\nGio thi nho di hop day du, dung co cup nha ong chau!"
    REGISTRATION_REJECTED = "Oof! Acc bi reject mat roi...\n\nChac admin thay bro sussy. Try again later nha!"
    NEW_USER_REQUEST = (
        "YEU CAU DUYET USER MOI\n"
        "====================\n\n"
        "User ID: {user_id}\n"
        "Ten: {name}\n"
        "Thoi gian: {time}\n\n"
        "Duyet hay tu choi?"
    )
    ACCOUNT_BANNED = "BRO TOANG ROI! Acc bi ban mat roi!\n\nXin admin di, nho cung tra sua may ra duoc unban!"
    
    # Check-in/Check-out
    CHECKIN_SUCCESS = (
        "SHEESH! Diem danh thanh cong!\n\n"
        "Time: {time}\n"
        "Buoi hop: {meeting}\n"
        "Dia diem: {location}\n\n"
        "Nho checkout de nhan diem nha!"
    )
    CHECKIN_ALREADY = "Bro oi diem danh roi ma con diem chi?\n\nDa check luc: {time}"
    CHECKOUT_SUCCESS = (
        "NICE! Check-out thanh cong!\n\n"
        "Time: {time}\n"
        "Diem nhan duoc: +{points} diem\n\n"
        "Ve chill thoi bro! GG!"
    )
    CHECKOUT_NOT_CHECKED_IN = "Ua? Check-out cai gi? Bro chua diem danh ma!"
    NO_ACTIVE_MEETING = "Hom nay khong co buoi hop nao dang dien ra!\n\nChill di bro!"
    
    # Status (gộp status + history)
    STATUS_TEMPLATE = (
        "THONG TIN CUA BAN\n"
        "====================\n\n"
        "Ten: {name}\n"
        "Diem thang nay: {monthly_points}\n"
        "Tong diem ky: {total_points}\n"
        "Rank: #{rank} - {rank_title}\n"
        "Muc CC thang: {cc_month}\n"
        "Muc CC ky: {cc_term}\n"
        "====================\n\n"
        "Dung /minhchung de gui minh chung cong viec!"
    )
    
    # Evidence (Minh chung)
    EVIDENCE_PROMPT = (
        "GUI MINH CHUNG CONG VIEC\n\n"
        "Gui 1 anh chup + mo ta cong viec + so diem yeu cau.\n\n"
        "Diem theo quy dinh:\n"
        "  +5: Tham gia hoat dong tai C1-101\n"
        "  +10: Ho tro dien gia\n"
        "  +15: Hoat dong ngoai khoa lon\n\n"
        "Format: Chup anh -> Gui anh kem caption\n"
        "Caption: [Mo ta] - [So diem]\n"
        "VD: Ho tro dien gia hoi thao AI - 10"
    )
    EVIDENCE_SUBMITTED = (
        "Da gui minh chung!\n\n"
        "Mo ta: {description}\n"
        "Diem yeu cau: {points}\n\n"
        "Doi admin duyet nha!"
    )
    EVIDENCE_APPROVED = "Minh chung #{id} da duoc duyet!\n+{points} diem"
    EVIDENCE_REJECTED = "Minh chung #{id} bi tu choi!\nLy do: {reason}"
    
    # Admin
    ADMIN_ONLY = "Lenh nay chi danh cho Admin!\n\nBro khong du power dau! No cap!"
    
    # Meeting
    MEETING_CREATED = (
        "Da tao buoi hop moi!\n\n"
        "{meeting_info}\n\n"
        "Gui thong bao den tat ca thanh vien?"
    )
    MEETING_NOTIFICATION = (
        "THONG BAO LICH HOP\n"
        "====================\n\n"
        "{meeting_info}\n\n"
        "Nho tham gia dung gio nha!"
    )
    
    # Ranking
    RANKING_HEADER = (
        "BANG XEP HANG THANG {month}/{year}\n"
        "====================\n\n"
    )
    RANKING_ITEM = "#{rank} {name}: {points} diem ({cc_level})\n"
    
    # Help
    HELP = (
        "HUONG DAN SU DUNG BOT\n"
        "====================\n\n"
        "LENH CO BAN:\n"
        "  /checkin - Diem danh buoi hop\n"
        "  /checkout - Check-out (nhan diem)\n"
        "  /status - Xem diem va xep hang\n"
        "  /ranking - Bang xep hang thang\n"
        "  /minhchung - Gui minh chung cong viec\n"
        "  /help - Xem huong dan\n\n"
        "QUY DINH DIEM:\n"
        "  +5: Hop thuong tai C1-101\n"
        "  +10: Ho tro dien gia\n"
        "  +15: Hoat dong ngoai khoa lon\n"
        "  -3: Khong dat bai quy che check-in\n"
        "  -10: Dang ky nhung khong tham gia\n\n"
        "LUU Y:\n"
        "  Phai check-in VA check-out moi co diem!\n"
        "  Diem reset moi thang.\n"
        "  Duoi 15 diem/thang = nang canh bao!"
    )
    HELP_ADMIN = (
        "\n\nLENH ADMIN:\n"
        "  /set_meeting - Tao buoi hop (nhap ten, thoi gian, gui GPS, chon loai)\n"
        "  /list_meetings - Danh sach buoi hop\n"
        "  /delete_meeting <id> - Xoa buoi hop (dong thoi vo hieu hoa dia diem)\n"
        "  /list_users - Danh sach thanh vien\n"
        "  /list_pending - Cho duyet\n"
        "  /ranking - Bang xep hang\n"
        "  /today - Bao cao hom nay\n"
        "  /export - Xuat Excel\n"
        "  /broadcast - Gui thong bao\n"
        "  /approve <id> - Duyet user\n"
        "  /reject <id> - Tu choi user\n"
        "  /ban <id> - Cam user\n"
        "  /unban <id> - Bo cam"
    )


class KeyboardLabels:
    """Vietnamese labels for keyboard buttons."""
    
    # Main menu
    CHECKIN = "Diem danh"
    CHECKOUT = "Check-out"
    STATUS = "Thong tin"
    MINHCHUNG = "Minh chung"
    
    # Actions
    CANCEL = "Huy"
    CONFIRM = "Xac nhan"
    
    # Admin
    APPROVE = "Duyet"
    REJECT = "Tu choi"
    LIST_USERS = "Thanh vien"
    LIST_PENDING = "Cho duyet"
    TODAY_REPORT = "Hom nay"
    EXPORT = "Xuat Excel"
    BROADCAST = "Thong bao"
    MEETINGS = "Buoi hop"
    RANKING = "Xep hang"
