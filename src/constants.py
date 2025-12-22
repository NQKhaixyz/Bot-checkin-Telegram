"""Constants for Telegram Attendance Bot."""


class Commands:
    """Bot command constants."""
    
    # User commands
    START = "start"
    HELP = "help"
    CHECKIN = "checkin"
    CHECKOUT = "checkout"
    STATUS = "status"
    HISTORY = "history"
    
    # Admin commands
    APPROVE = "approve"
    REJECT = "reject"
    BAN = "ban"
    UNBAN = "unban"
    LIST_USERS = "list_users"
    LIST_PENDING = "list_pending"
    SET_LOCATION = "set_location"
    LIST_LOCATIONS = "list_locations"
    TODAY = "today"
    EXPORT = "export"
    BROADCAST = "broadcast"


class CallbackData:
    """Callback data prefixes for inline keyboards."""
    
    CHECKIN = "checkin"
    CHECKOUT = "checkout"
    APPROVE_USER = "approve_user"
    REJECT_USER = "reject_user"
    CONFIRM_LOCATION = "confirm_location"
    CANCEL = "cancel"
    
    @staticmethod
    def make(prefix: str, *args) -> str:
        """Create callback data string from prefix and arguments."""
        if args:
            return f"{prefix}:{':'.join(str(arg) for arg in args)}"
        return prefix
    
    @staticmethod
    def parse(data: str) -> tuple[str, list[str]]:
        """Parse callback data into prefix and arguments."""
        parts = data.split(":")
        return parts[0], parts[1:] if len(parts) > 1 else []


class Messages:
    """Vietnamese message templates - Gen Z style 🔥💀."""
    
    # Welcome & Registration
    WELCOME = (
        "🎉 Yo yo yo! Welcome to CLB Điểm Danh nha bestie!\n\n"
        "☕ Chill đi, đợi admin duyệt tí thôi!\n"
        "🐌 Ông admin hơi chill nên từ từ nha, đừng có gấp quá xíu lú 😏"
    )
    WELCOME_BACK = "👋 Ủa bro quay lại rồi à? Lâu quá không gặp, nhớ ghê luôn á! 😎✨"
    REGISTRATION_PENDING = "⏳ Acc đang pending nha! Admin đang touchgrass 🧋 Chill xíu đi bestie!"
    ALREADY_REGISTERED = "🙄 Alo? Đăng ký rồi còn spam chi nữa bro?\n\n📋 Status: {status}\n\n🤦 Não cá vàng real đấy! 💀"
    REGISTRATION_APPROVED = "🎊 LET'S GOOO! Acc được duyệt rồi nha!\n\n🏃 Giờ thì nhớ đi họp đầy đủ, đừng có cúp nha ông cháu! 💪🔥"
    REGISTRATION_REJECTED = "😢 Oof! Acc bị reject mất rồi...\n\n🤔 Chắc admin thấy bro sussy. Try again later nha! 🍀"
    ACCOUNT_BANNED = "🚫 BRO TOANG RỒI! Acc bị ban mất rồi!\n\n📞 Xin admin đi, nhớ cúng trà sữa 🧋 may ra được unban!"
    
    # Check-in
    CHECKIN_REQUEST_LOCATION = "📍 Gửi location để điểm danh nè bro!\n\n⚠️ Đừng có fake loc nha, Bot slay lắm đó! 🕵️💅"
    CHECKIN_SUCCESS = "✅ SHEESH! Điểm danh thành công!\n\n🕐 Time: {time}\n📍 Location: {location}\n\n💪 Bro chăm quá xá luôn! Respect! 🫡🔥"
    CHECKIN_ALREADY = "🙄 Bro ơi điểm danh rồi mà còn điểm chi?\n\n🕐 Đã check lúc: {time}\n\n🧠 7 giây quên luôn á? Goldfish brain real! 🐟💀"
    CHECKIN_FAILED = "❌ Oof! Điểm danh failed!\n\n🔧 Server đang nằm nghỉ. Try again later nha! 😴"
    CHECKIN_INVALID_LOCATION = "❌ Ê ê đừng có sussy baka! 🕵️\n\nLocation này có mùi 'chăn ấm đệm êm' lắm nha bro.\n\n🏃 Vác xác đến chỗ họp đi rồi tính!"
    CHECKIN_TOO_FAR = (
        "❌ Ủa bro đang ở đâu vậy? Mars à? 🚀💀\n\n"
        "📏 Khoảng cách: {distance}m\n"
        "📍 Địa điểm họp: {location}\n\n"
        "🏃‍♂️ Di chuyển lại gần đi bro!\n"
        "🧋 Bot chỉ thấy mùi trà sữa xung quanh thôi, không thấy phòng họp đâu luôn!"
    )
    
    # Check-out  
    CHECKOUT_REQUEST_LOCATION = "📍 Gửi location để check-out nè!\n\n🏃 Họp xong rồi hả? GG! 🎉"
    CHECKOUT_SUCCESS = (
        "✅ NICE! Check-out thành công!\n\n"
        "🕐 Điểm danh: {checkin_time}\n"
        "🕐 Check-out: {checkout_time}\n"
        "⏱️ Thời gian họp: {duration}\n\n"
        "🎉 Cảm ơn bro đã tham gia! Slay quá đi! 💅\n"
        "🛋️ Về chill thôi nào~ 🍻✨"
    )
    CHECKOUT_NOT_CHECKED_IN = "🤨 Ủa? Check-out cái gì? Bro chưa điểm danh mà!\n\n🛏️ Đừng nói là cúp họp nằm nhà nha? Real sussy đó! 😏💀"
    CHECKOUT_ALREADY = "🙄 Bro check-out rồi còn check chi nữa?\n\n🕐 Đã checkout lúc: {time}\n\n🏠 Go home bro! Sao vẫn còn ở đây? 🤔"
    CHECKOUT_FAILED = "❌ Check-out failed!\n\n😱 CLB muốn giữ bro lại họp thêm. RIP! Try again! 🏃💀"
    CHECKOUT_INVALID_LOCATION = "❌ Sai location rồi bestie ơi! 😤\n\nTeleport chưa được buff đâu nha.\n\n🏃 Vác xác về đúng chỗ lẹ lên!"
    
    # Location
    LOCATION_RECEIVED = "📍 Got it! Đang process... 🔄"
    LOCATION_CANCELLED = "❌ Đã cancel! Nhát quá bro ơi! 😏💀"
    LOCATION_TIMEOUT = "⏰ Hết time rồi bro!\n\n🐌 Chậm như rùa vậy? Speed up! 🏃🔥"
    LOCATION_SET_SUCCESS = "✅ Set location thành công!\n\n📍 Name: {name}\n🌐 Tọa độ: {lat}, {lon}\n📏 Radius: {radius}m\n\n🎯 Giờ thì không ai trốn họp được! Muahaha 😈🔥"
    LOCATION_LIST_HEADER = "📍 List địa điểm họp:\n\n🔒 Các spot 'giam' thành viên:\n"
    LOCATION_LIST_EMPTY = "📍 Chưa có location nào!\n\n🤔 Admin ơi quên set location rồi kìa! 💀"
    LOCATION_LIST_ITEM = "  🏢 {name}: {lat}, {lon} (radius {radius}m)"
    
    # Status
    STATUS_NOT_CHECKED_IN = "📊 Status hôm nay:\n\n❌ Chưa điểm danh!\n\n🛏️ Định cúp họp hả bro? Dậy đi! ⏰💀"
    STATUS_CHECKED_IN = (
        "📊 Status hôm nay:\n\n"
        "✅ Đã điểm danh!\n"
        "🕐 Time: {checkin_time}\n"
        "📍 Location: {location}\n\n"
        "💪 Thành viên chăm xỉu! Based! 🫡🔥"
    )
    STATUS_CHECKED_OUT = (
        "📊 Status hôm nay:\n\n"
        "✅ Điểm danh: {checkin_time}\n"
        "✅ Check-out: {checkout_time}\n"
        "⏱️ Thời gian: {duration}\n\n"
        "🎉 Done! Về chill thôi bro! GG! 🍻✨"
    )
    
    # History
    HISTORY_HEADER = "📜 Lịch sử điểm danh:\n\n📚 Evidence bro có đi họp:\n"
    HISTORY_EMPTY = "📜 Chưa có history!\n\n🤔 Bro có phải member CLB không vậy? Sus quá! 👀💀"
    HISTORY_ITEM = "📅 {date}\n   ⏰ In: {checkin}\n   🏃 Out: {checkout}\n   ⏱️ Duration: {duration}\n"
    
    # Admin messages
    ADMIN_NEW_USER = (
        "👤 CÓ NEWBIE NÈ!\n\n"
        "🆔 ID: {user_id}\n"
        "👤 Name: {full_name}\n"
        "📱 Username: @{username}\n\n"
        "🤔 Admin ơi, approve hay reject đây? 🎰"
    )
    NEW_USER_REQUEST = (
        "👤 New member request!\n\n"
        "🆔 ID: {user_id}\n"
        "👤 Name: {name}\n"
        "🕐 Time: {time}\n\n"
        "⚖️ Số phận bro này nằm trong tay Admin! 😈🔥"
    )
    ADMIN_USER_APPROVED = "✅ Đã approve {full_name} (ID: {user_id})!\n\n😇 Welcome newbie vào CLB! Let's go! 💪🔥"
    ADMIN_USER_REJECTED = "❌ Đã reject {full_name} (ID: {user_id})!\n\n😢 Not based enough! Bye bye! 👋💀"
    ADMIN_USER_BANNED = "🚫 Đã BAN {full_name} (ID: {user_id})!\n\n⚰️ RIP bozo! Get rekt! 🪦💀"
    ADMIN_USER_UNBANNED = "✅ Đã UNBAN {full_name} (ID: {user_id})!\n\n🎉 Redemption arc! Welcome back bro! 🙏✨"
    ADMIN_USER_NOT_FOUND = "❌ Không tìm thấy member!\n\n👻 Ghost à? Check lại ID đi admin! 💀"
    ADMIN_LIST_USERS_HEADER = "👥 List thành viên CLB:\n\n📋 The squad:\n"
    ADMIN_LIST_USERS_EMPTY = "👥 CLB chưa có ai cả!\n\n🏜️ Lonely admin moment! 😢💀"
    ADMIN_LIST_USERS_ITEM = "  👤 {full_name} (@{username}) - {status}"
    ADMIN_LIST_PENDING_HEADER = "⏳ Đang chờ duyệt:\n\n🐑 Queue đang dài nè:\n"
    ADMIN_LIST_PENDING_EMPTY = "✅ Không có ai pending!\n\n😴 Admin rảnh rồi, đi touch grass thôi! 🧋🌿"
    ADMIN_TODAY_HEADER = "📊 Điểm danh hôm nay:\n\n📈 Ai based ai sussy:\n"
    ADMIN_TODAY_EMPTY = "📊 Chưa có ai điểm danh!\n\n😱 Cả CLB cúp họp hả? Ded server! 🤖💀"
    ADMIN_TODAY_ITEM = "  👤 {full_name}: {checkin} - {checkout}"
    ADMIN_EXPORT_SUCCESS = "📁 Export thành công!\n\n📊 Evidence để... xử lý mấy đứa cúp họp! 💰😈"
    ADMIN_EXPORT_FAILED = "❌ Export failed!\n\n🔧 Server đang đình công! Try again later! 💀"
    ADMIN_BROADCAST_SUCCESS = "📢 Đã spam {count} members!\n\n📣 Admin has spoken! 🔊🔥"
    ADMIN_BROADCAST_PROMPT = "📢 Nhập content thông báo:\n\n✍️ Think twice before sending nha, no take backs! 😏"
    ADMIN_ONLY = "⚠️ Lệnh này chỉ dành cho Admin!\n\n👑 Bro không đủ power đâu! No cap! 🚫💀"
    
    # Errors
    ERROR_GENERAL = "❌ Oof! Có bug!\n\n🔧 Server đang... having a moment. Try again later! 🧘💀"
    ERROR_UNAUTHORIZED = "⚠️ Bro không có quyền!\n\n🚫 Đừng có sussy nha! 👮💀"
    ERROR_INVALID_COMMAND = "❌ Invalid command!\n\n🤖 Bot không hiểu bro nói gì! Speak human pls! 🤷💀"
    ERROR_INVALID_INPUT = "❌ Input sai rồi!\n\n🙈 Read the docs rồi try again nha bro!"
    ERROR_DATABASE = "❌ Database error!\n\n💾 Data đang... đi chơi. BRB! 🏃💀"
    
    # Help
    HELP = (
        "📖 GUIDE - CLB ĐIỂM DANH\n\n"
        "🏃 Basic commands:\n"
        "  /checkin - Điểm danh đi họp\n"
        "  /checkout - Check-out về\n"
        "  /status - Xem status hôm nay\n"
        "  /history - Xem history tháng này\n"
        "  /help - Xem guide này\n\n"
        "⚠️ LƯU Ý:\n"
        "  • Phải ở đúng location mới điểm danh được\n"
        "  • Đừng fake loc, Bot slay lắm! 🕵️💅\n"
        "  • Điểm danh xong nhớ checkout nha!\n\n"
        "💪 Good luck! Đừng có ngủ gật là được! 😅🔥"
    )
    HELP_ADMIN = (
        "\n\n👑 ADMIN COMMANDS (For the chosen ones):\n\n"
        "👥 Quản lý members:\n"
        "  /approve <id> - Duyệt member\n"
        "  /reject <id> - Reject member\n"
        "  /ban <id> - Ban member\n"
        "  /unban <id> - Unban member\n"
        "  /list_users - List all members\n"
        "  /list_pending - List pending\n\n"
        "📍 Quản lý locations:\n"
        "  /set_location - Set new location\n"
        "  /list_locations - List locations\n\n"
        "📊 Reports:\n"
        "  /today - Today's attendance\n"
        "  /export - Export Excel\n"
        "  /broadcast - Spam all 📢\n\n"
        "😈 Ultimate power! No cap! 🔥"
    )
    
    # Confirmation
    CONFIRM_ACTION = "❓ Sure chưa? No take backs đâu nha! 🤔"
    ACTION_CANCELLED = "❌ Cancelled! Chicken! 😏🐔"
    ACTION_CONFIRMED = "✅ Done! No regrets? 😎🔥"


class KeyboardLabels:
    """Vietnamese labels for keyboard buttons."""
    
    # Main menu
    CHECKIN = "📥 Điểm danh"
    CHECKOUT = "📤 Check-out"
    STATUS = "📊 Status"
    HISTORY = "📜 History"
    
    # Location
    SHARE_LOCATION = "📍 Gửi vị trí"
    CANCEL = "❌ Cancel"
    
    # Confirmation
    CONFIRM = "✅ Confirm"
    
    # Admin
    APPROVE = "✅ Approve"
    REJECT = "❌ Reject"
    LIST_USERS = "👥 Members"
    LIST_PENDING = "⏳ Pending"
    TODAY_REPORT = "📊 Today"
    EXPORT = "📁 Export"
    BROADCAST = "📢 Broadcast"
    LOCATIONS = "📍 Locations"
