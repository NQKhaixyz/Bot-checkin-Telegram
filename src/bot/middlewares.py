"""
Middleware decorators for Telegram Attendance Bot handlers.

Provides authentication, authorization, and logging decorators.
"""

from __future__ import annotations

import functools
import logging
from typing import Any, Callable, Coroutine, Optional, TypeVar, Union

from telegram import Update
from telegram.ext import ContextTypes

from src.config import get_config
from src.database import User, UserRole, UserStatus, get_db_session

logger = logging.getLogger(__name__)

# Type aliases for handler functions
HandlerFunc = Callable[..., Coroutine[Any, Any, Any]]
F = TypeVar("F", bound=HandlerFunc)


def require_registration(handler: F) -> F:
    """
    Decorator that checks if user is registered in the database.
    
    Passes the User object as the 'user' keyword argument to the handler.
    If user is not registered, sends a message prompting registration.
    
    Args:
        handler: The async handler function to wrap.
        
    Returns:
        The wrapped handler function.
        
    Example:
        @require_registration
        async def my_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, user: User):
            await update.message.reply_text(f"Hello, {user.full_name}!")
    """
    @functools.wraps(handler)
    async def wrapper(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        if not update.effective_user:
            logger.warning("Update has no effective_user")
            return None
            
        user_id = update.effective_user.id
        
        with get_db_session() as db:
            user = db.query(User).filter(User.user_id == user_id).first()
            
            if user is None:
                if update.message:
                    await update.message.reply_text(
                        "You are not registered. Please use /start to register."
                    )
                elif update.callback_query:
                    await update.callback_query.answer(
                        "You are not registered. Please use /start to register.",
                        show_alert=True,
                    )
                return None
            
            # Detach user from session to use outside context manager
            db.expunge(user)
        
        # Pass user object to handler
        kwargs["user"] = user
        return await handler(update, context, *args, **kwargs)
    
    return wrapper  # type: ignore[return-value]


def require_active(handler: F) -> F:
    """
    Decorator that checks if user is active (not pending or banned).
    
    Must be used after @require_registration decorator.
    
    Args:
        handler: The async handler function to wrap.
        
    Returns:
        The wrapped handler function.
        
    Example:
        @require_registration
        @require_active
        async def my_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, user: User):
            await update.message.reply_text("You are an active user!")
    """
    @functools.wraps(handler)
    async def wrapper(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        user: Optional[User] = kwargs.get("user")
        
        if user is None:
            # This shouldn't happen if decorators are applied correctly
            logger.error("require_active called without user in kwargs. "
                        "Make sure @require_registration is applied first.")
            if update.message:
                await update.message.reply_text(
                    "An error occurred. Please try again."
                )
            return None
        
        if user.status == UserStatus.PENDING:
            message = (
                "Your registration is pending approval. "
                "Please wait for an admin to approve your request."
            )
            if update.message:
                await update.message.reply_text(message)
            elif update.callback_query:
                await update.callback_query.answer(message, show_alert=True)
            return None
        
        if user.status == UserStatus.BANNED:
            message = "Your account has been banned. Please contact an administrator."
            if update.message:
                await update.message.reply_text(message)
            elif update.callback_query:
                await update.callback_query.answer(message, show_alert=True)
            return None
        
        return await handler(update, context, *args, **kwargs)
    
    return wrapper  # type: ignore[return-value]


def require_admin(handler: F) -> F:
    """
    Decorator that checks if user is an admin.
    
    Checks both database role and config super admin list.
    Must be used after @require_registration decorator.
    
    Args:
        handler: The async handler function to wrap.
        
    Returns:
        The wrapped handler function.
        
    Example:
        @require_registration
        @require_admin
        async def admin_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, user: User):
            await update.message.reply_text("Admin action executed!")
    """
    @functools.wraps(handler)
    async def wrapper(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        user: Optional[User] = kwargs.get("user")
        
        if user is None:
            logger.error("require_admin called without user in kwargs. "
                        "Make sure @require_registration is applied first.")
            if update.message:
                await update.message.reply_text(
                    "An error occurred. Please try again."
                )
            return None
        
        config = get_config()
        is_super_admin = config.admin.is_super_admin(user.user_id)
        is_db_admin = user.role == UserRole.ADMIN
        
        if not is_super_admin and not is_db_admin:
            message = "You don't have permission to use this command."
            if update.message:
                await update.message.reply_text(message)
            elif update.callback_query:
                await update.callback_query.answer(message, show_alert=True)
            logger.warning(
                f"Unauthorized admin access attempt by user {user.user_id} ({user.full_name})"
            )
            return None
        
        return await handler(update, context, *args, **kwargs)
    
    return wrapper  # type: ignore[return-value]


def log_action(action_name: str) -> Callable[[F], F]:
    """
    Decorator factory that logs handler actions.
    
    Args:
        action_name: The name of the action to log.
        
    Returns:
        A decorator function.
        
    Example:
        @log_action("check_in")
        async def check_in_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
            # Handler implementation
            pass
    """
    def decorator(handler: F) -> F:
        @functools.wraps(handler)
        async def wrapper(
            update: Update,
            context: ContextTypes.DEFAULT_TYPE,
            *args: Any,
            **kwargs: Any,
        ) -> Any:
            user_id: Optional[int] = None
            username: Optional[str] = None
            
            if update.effective_user:
                user_id = update.effective_user.id
                username = update.effective_user.full_name or update.effective_user.username
            
            logger.info(
                f"Action '{action_name}' started by user {user_id} ({username})"
            )
            
            try:
                result = await handler(update, context, *args, **kwargs)
                logger.info(
                    f"Action '{action_name}' completed successfully for user {user_id}"
                )
                return result
            except Exception as e:
                logger.error(
                    f"Action '{action_name}' failed for user {user_id}: {e}",
                    exc_info=True,
                )
                raise
        
        return wrapper  # type: ignore[return-value]
    
    return decorator


__all__ = [
    "require_registration",
    "require_active",
    "require_admin",
    "log_action",
]
