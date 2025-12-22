"""Keyboard utilities for Telegram Attendance Bot."""

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

from src.constants import CallbackData, KeyboardLabels


class Keyboards:
    """Keyboard factory for creating bot keyboards."""
    
    @staticmethod
    def main_menu() -> ReplyKeyboardMarkup:
        """Create main menu keyboard with Check-in, Check-out, Status, History."""
        keyboard = [
            [
                KeyboardButton(KeyboardLabels.CHECKIN),
                KeyboardButton(KeyboardLabels.CHECKOUT),
            ],
            [
                KeyboardButton(KeyboardLabels.STATUS),
                KeyboardButton(KeyboardLabels.HISTORY),
            ],
        ]
        return ReplyKeyboardMarkup(
            keyboard,
            resize_keyboard=True,
            one_time_keyboard=False,
        )
    
    @staticmethod
    def request_location() -> ReplyKeyboardMarkup:
        """Create keyboard with location request button and cancel."""
        keyboard = [
            [
                KeyboardButton(
                    KeyboardLabels.SHARE_LOCATION,
                    request_location=True,
                ),
            ],
            [
                KeyboardButton(KeyboardLabels.CANCEL),
            ],
        ]
        return ReplyKeyboardMarkup(
            keyboard,
            resize_keyboard=True,
            one_time_keyboard=True,
        )
    
    @staticmethod
    def admin_menu() -> ReplyKeyboardMarkup:
        """Create admin menu keyboard with admin options."""
        keyboard = [
            [
                KeyboardButton(KeyboardLabels.LIST_USERS),
                KeyboardButton(KeyboardLabels.LIST_PENDING),
            ],
            [
                KeyboardButton(KeyboardLabels.TODAY_REPORT),
                KeyboardButton(KeyboardLabels.EXPORT),
            ],
            [
                KeyboardButton(KeyboardLabels.LOCATIONS),
                KeyboardButton(KeyboardLabels.BROADCAST),
            ],
            [
                KeyboardButton(KeyboardLabels.CHECKIN),
                KeyboardButton(KeyboardLabels.CHECKOUT),
            ],
            [
                KeyboardButton(KeyboardLabels.STATUS),
                KeyboardButton(KeyboardLabels.HISTORY),
            ],
        ]
        return ReplyKeyboardMarkup(
            keyboard,
            resize_keyboard=True,
            one_time_keyboard=False,
        )
    
    @staticmethod
    def approve_reject_user(user_id: int) -> InlineKeyboardMarkup:
        """Create inline keyboard with approve/reject buttons for a user.
        
        Args:
            user_id: The user ID to approve or reject.
            
        Returns:
            InlineKeyboardMarkup with approve and reject buttons.
        """
        keyboard = [
            [
                InlineKeyboardButton(
                    KeyboardLabels.APPROVE,
                    callback_data=CallbackData.make(CallbackData.APPROVE_USER, user_id),
                ),
                InlineKeyboardButton(
                    KeyboardLabels.REJECT,
                    callback_data=CallbackData.make(CallbackData.REJECT_USER, user_id),
                ),
            ],
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def confirm_cancel() -> InlineKeyboardMarkup:
        """Create inline keyboard with confirm/cancel buttons."""
        keyboard = [
            [
                InlineKeyboardButton(
                    KeyboardLabels.CONFIRM,
                    callback_data=CallbackData.make(CallbackData.CONFIRM_LOCATION),
                ),
                InlineKeyboardButton(
                    KeyboardLabels.CANCEL,
                    callback_data=CallbackData.make(CallbackData.CANCEL),
                ),
            ],
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def remove() -> ReplyKeyboardRemove:
        """Remove the current reply keyboard."""
        return ReplyKeyboardRemove()
