"""
Location management handlers for admin users.

Handles setting up office locations via GPS coordinates.
"""

import logging
from telegram import Update, Message
from telegram.ext import (
    ContextTypes, 
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters
)

from src.services.geolocation import GeolocationService
from src.database import User
from src.constants import Messages, CallbackData
from src.bot.keyboards import Keyboards
from src.bot.middlewares import require_admin, require_registration, log_action
from src.config import config

logger = logging.getLogger(__name__)

# Conversation states
WAITING_FOR_LOCATION = 1
WAITING_FOR_NAME = 2
WAITING_FOR_RADIUS = 3

# Temporary storage for location setup
location_setup_data = {}


@require_registration
@require_admin
@log_action("set_location_start")
async def set_location_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user: User = None
) -> int:
    """
    Handle /set_location command.
    
    Starts the location setup conversation.
    
    Returns:
        Conversation state WAITING_FOR_LOCATION
    """
    user_id = update.effective_user.id
    
    # Clear any previous setup data
    location_setup_data[user_id] = {}
    
    await update.message.reply_text(
        "Thiet lap dia diem van phong moi.\n\n"
        "Buoc 1/3: Vui long gui vi tri GPS cua van phong:",
        reply_markup=Keyboards.request_location()
    )
    
    return WAITING_FOR_LOCATION


async def receive_location_for_setup(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> int:
    """
    Receive GPS location for new office setup.
    
    Stores coordinates and asks for location name.
    
    Returns:
        Conversation state WAITING_FOR_NAME
    """
    user_id = update.effective_user.id
    location = update.message.location
    
    # Store coordinates
    location_setup_data[user_id] = {
        "latitude": location.latitude,
        "longitude": location.longitude
    }
    
    # Format for display
    coords = GeolocationService.format_coordinates(
        location.latitude, location.longitude
    )
    maps_link = GeolocationService.get_google_maps_link(
        location.latitude, location.longitude
    )
    
    await update.message.reply_text(
        f"Da nhan vi tri:\n{coords}\n\n"
        f"Xem tren Google Maps: {maps_link}\n\n"
        "Buoc 2/3: Vui long nhap ten cho dia diem nay\n"
        "(Vi du: VP Ha Noi, Chi nhanh HCM, ...):",
        reply_markup=Keyboards.remove()
    )
    
    return WAITING_FOR_NAME


async def receive_location_name(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> int:
    """
    Receive location name during setup.
    
    Stores name and asks for geofence radius.
    
    Returns:
        Conversation state WAITING_FOR_RADIUS
    """
    user_id = update.effective_user.id
    name = update.message.text.strip()
    
    # Validate name
    if len(name) < 2:
        await update.message.reply_text(
            "Ten qua ngan. Vui long nhap lai:"
        )
        return WAITING_FOR_NAME
    
    if len(name) > 100:
        await update.message.reply_text(
            "Ten qua dai. Vui long nhap lai (toi da 100 ky tu):"
        )
        return WAITING_FOR_NAME
    
    # Store name
    location_setup_data[user_id]["name"] = name
    
    await update.message.reply_text(
        f"Ten dia diem: {name}\n\n"
        f"Buoc 3/3: Vui long nhap ban kinh cho phep (met)\n"
        f"(Khoang cach toi da tu van phong de check-in thanh cong)\n\n"
        f"Vi du: 50 (cho phep check-in trong vong 50 met)\n"
        f"Mac dinh: {config.attendance.geofence_default_radius}m"
    )
    
    return WAITING_FOR_RADIUS


async def receive_radius(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> int:
    """
    Receive geofence radius and complete location setup.
    
    Creates the location in database and confirms to admin.
    
    Returns:
        ConversationHandler.END
    """
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    # Parse radius
    try:
        radius = int(text)
        if radius <= 0:
            raise ValueError("Radius must be positive")
        if radius > 10000:  # Max 10km
            raise ValueError("Radius too large")
    except ValueError:
        await update.message.reply_text(
            "Gia tri khong hop le. Vui long nhap so nguyen duong (1-10000):"
        )
        return WAITING_FOR_RADIUS
    
    # Get stored data
    data = location_setup_data.get(user_id, {})
    
    if not data.get("latitude") or not data.get("name"):
        await update.message.reply_text(
            "Loi: Thieu du lieu. Vui long bat dau lai voi /set_location"
        )
        return ConversationHandler.END
    
    # Create location
    try:
        location = GeolocationService.create_location(
            name=data["name"],
            latitude=data["latitude"],
            longitude=data["longitude"],
            radius=radius,
            created_by=user_id
        )
        
        # Clean up
        del location_setup_data[user_id]
        
        await update.message.reply_text(
            Messages.LOCATION_SET_SUCCESS.format(
                name=location.name,
                lat=location.latitude,
                lon=location.longitude,
                radius=location.radius
            ),
            reply_markup=Keyboards.admin_menu()
        )
        
        logger.info(
            f"Admin {user_id} created location: {location.name} "
            f"at ({location.latitude}, {location.longitude})"
        )
        
    except Exception as e:
        logger.error(f"Failed to create location: {e}")
        await update.message.reply_text(
            f"Loi khi tao dia diem: {str(e)}"
        )
    
    return ConversationHandler.END


async def cancel_location_setup(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Cancel location setup conversation."""
    user_id = update.effective_user.id
    
    # Clean up
    if user_id in location_setup_data:
        del location_setup_data[user_id]
    
    await update.message.reply_text(
        "Da huy thiet lap dia diem.",
        reply_markup=Keyboards.admin_menu()
    )
    
    return ConversationHandler.END


# Location setup conversation handler
location_setup_conversation = ConversationHandler(
    entry_points=[
        CommandHandler("set_location", set_location_command)
    ],
    states={
        WAITING_FOR_LOCATION: [
            MessageHandler(filters.LOCATION, receive_location_for_setup)
        ],
        WAITING_FOR_NAME: [
            MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                receive_location_name
            )
        ],
        WAITING_FOR_RADIUS: [
            MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                receive_radius
            )
        ]
    },
    fallbacks=[
        CommandHandler("cancel", cancel_location_setup),
        MessageHandler(filters.COMMAND, cancel_location_setup)
    ],
    allow_reentry=True
)
