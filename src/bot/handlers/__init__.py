"""
Bot handlers package.

Exports all handler functions for registration.
"""

# Start/Registration handlers
from .start import (
    start_command,
    registration_conversation,
    WAITING_FOR_NAME,
)

# Check-in/Check-out handlers
from .checkin import (
    checkin_conversation,
    checkout_command,
    status_command,
    cancel_action,
    CHECKIN_WAITING_FOR_LOCATION,
)

# Menu handler
from .menu import text_message_handler

# Admin handlers
from .admin import (
    approve_command,
    reject_command,
    ban_command,
    unban_command,
    list_users_command,
    list_pending_command,
    broadcast_command,
    today_command,
    export_command,
    stats_command,
    help_admin_command,
    admin_callback_handler,
    list_locations_command,
    delete_location_command,
    list_meetings_command,
    ranking_command,
)

# Location handlers
from .location import (
    set_location_command,
    location_setup_conversation,
    WAITING_FOR_LOCATION,
    WAITING_FOR_NAME as LOCATION_WAITING_FOR_NAME,
    WAITING_FOR_RADIUS,
)

# Evidence handlers
from .evidence import (
    evidence_conversation,
    minhchung_command,
    WAITING_FOR_PHOTO,
)

# Help handler
from .help import help_command

# Error handler
from .error import error_handler

__all__ = [
    # Start
    "start_command",
    "registration_conversation",
    "WAITING_FOR_NAME",
    # Check-in
    "checkin_conversation",
    "CHECKIN_WAITING_FOR_LOCATION",
    "checkout_command",
    "status_command",
    "cancel_action",
    # Menu
    "text_message_handler",
    # Admin
    "approve_command",
    "reject_command",
    "ban_command",
    "unban_command",
    "list_users_command",
    "list_pending_command",
    "broadcast_command",
    "today_command",
    "export_command",
    "stats_command",
    "help_admin_command",
    "admin_callback_handler",
    "list_locations_command",
    "delete_location_command",
    "list_meetings_command",
    "ranking_command",
    # Location
    "set_location_command",
    "location_setup_conversation",
    "WAITING_FOR_LOCATION",
    "LOCATION_WAITING_FOR_NAME",
    "WAITING_FOR_RADIUS",
    # Evidence
    "evidence_conversation",
    "minhchung_command",
    "WAITING_FOR_PHOTO",
    # Help
    "help_command",
    # Error
    "error_handler",
]
