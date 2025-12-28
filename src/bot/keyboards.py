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
        """Create main menu keyboard."""
        keyboard = [
            [
                KeyboardButton(KeyboardLabels.CHECKIN),
                KeyboardButton(KeyboardLabels.CHECKOUT),
            ],
            [
                KeyboardButton(KeyboardLabels.STATUS),
                KeyboardButton(KeyboardLabels.MINHCHUNG),
            ],
        ]
        return ReplyKeyboardMarkup(
            keyboard,
            resize_keyboard=True,
            one_time_keyboard=False,
        )
    
    @staticmethod
    def admin_menu() -> ReplyKeyboardMarkup:
        """Create admin menu keyboard."""
        keyboard = [
            [
                KeyboardButton(KeyboardLabels.CHECKIN),
                KeyboardButton(KeyboardLabels.CHECKOUT),
            ],
            [
                KeyboardButton(KeyboardLabels.STATUS),
                KeyboardButton(KeyboardLabels.MINHCHUNG),
            ],
            [
                KeyboardButton(KeyboardLabels.LIST_USERS),
                KeyboardButton(KeyboardLabels.LIST_PENDING),
            ],
            [
                KeyboardButton(KeyboardLabels.MEETINGS),
                KeyboardButton(KeyboardLabels.RANKING),
            ],
            [
                KeyboardButton(KeyboardLabels.TODAY_REPORT),
                KeyboardButton(KeyboardLabels.EXPORT),
            ],
        ]
        return ReplyKeyboardMarkup(
            keyboard,
            resize_keyboard=True,
            one_time_keyboard=False,
        )
    
    @staticmethod
    def cancel_only() -> ReplyKeyboardMarkup:
        """Create keyboard with cancel button only."""
        keyboard = [[KeyboardButton(KeyboardLabels.CANCEL)]]
        return ReplyKeyboardMarkup(
            keyboard,
            resize_keyboard=True,
            one_time_keyboard=True,
        )
    
    @staticmethod
    def approve_reject_user(user_id: int) -> InlineKeyboardMarkup:
        """Create inline keyboard with approve/reject buttons for a user."""
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
    def approve_reject_evidence(evidence_id: int) -> InlineKeyboardMarkup:
        """Create inline keyboard with approve/reject buttons for evidence."""
        keyboard = [
            [
                InlineKeyboardButton(
                    f"{KeyboardLabels.APPROVE}",
                    callback_data=CallbackData.make(CallbackData.APPROVE_EVIDENCE, evidence_id),
                ),
                InlineKeyboardButton(
                    f"{KeyboardLabels.REJECT}",
                    callback_data=CallbackData.make(CallbackData.REJECT_EVIDENCE, evidence_id),
                ),
            ],
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def register_meeting(meeting_id: int) -> InlineKeyboardMarkup:
        """Create inline keyboard to register for a meeting."""
        keyboard = [
            [
                InlineKeyboardButton(
                    "Dang ky tham gia",
                    callback_data=CallbackData.make(CallbackData.REGISTER_MEETING, meeting_id),
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
                    callback_data="confirm",
                ),
                InlineKeyboardButton(
                    KeyboardLabels.CANCEL,
                    callback_data=CallbackData.CANCEL,
                ),
            ],
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def request_location() -> ReplyKeyboardMarkup:
        """Create keyboard with location request button."""
        keyboard = [
            [KeyboardButton("Gui vi tri", request_location=True)],
            [KeyboardButton(KeyboardLabels.CANCEL)],
        ]
        return ReplyKeyboardMarkup(
            keyboard,
            resize_keyboard=True,
            one_time_keyboard=True,
        )
    
    @staticmethod
    def remove() -> ReplyKeyboardRemove:
        """Remove the current reply keyboard."""
        return ReplyKeyboardRemove()
