import logging
from telegram import Update
from telegram.ext import ContextTypes
from user_database import add_user, remove_user, get_all_users, get_user_by_username, increment_request_count, check_and_reset_request_counts, block_user, unblock_user, is_user_blocked

logger = logging.getLogger(__name__)

async def add_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id == 929527704:
        if context.args:
            new_user_id = int(context.args[0])
            nickname = context.args[1] if len(context.args) > 1 else ""
            username = context.args[2] if len(context.args) > 2 else ""
            add_user(new_user_id, nickname, username)
            await update.message.reply_text(f"Пользователь {new_user_id} добавлен.")
        else:
            await update.message.reply_text("Пожалуйста, укажите ID пользователя для добавления.")

async def remove_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id == 929527704:
        if context.args:
            remove_user_id = int(context.args[0])
            remove_user(remove_user_id)
            await update.message.reply_text(f"Пользователь {remove_user_id} удален.")
        else:
            await update.message.reply_text("Пожалуйста, укажите ID пользователя для удаления.")

async def block_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id == 929527704:
        if context.args:
            block_user_id = int(context.args[0])
            block_user(block_user_id)
            await update.message.reply_text(f"Пользователь {block_user_id} заблокирован.")
        else:
            await update.message.reply_text("Пожалуйста, укажите ID пользователя для блокировки.")

async def unblock_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id == 929527704:
        if context.args:
            unblock_user_id = int(context.args[0])
            unblock_user(unblock_user_id)
            await update.message.reply_text(f"Пользователь {unblock_user_id} разблокирован.")
        else:
            await update.message.reply_text("Пожалуйста, укажите ID пользователя для разблокировки.")

async def list_users_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id == 929527704:
        check_and_reset_request_counts()
        users = get_all_users()
        user_list_str = "\n".join([f"{user['id']} - {user['nickname']} - @{user['username']} - {user['request_count']} запросов - {'бан' if user['blocked'] == 'No' else 'активен'}" for user in users])
        await update.message.reply_text(f"Список пользователей:\n{user_list_str}")

async def send_message_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id == 929527704:
        if context.args and len(context.args) > 1:
            username = context.args[0]
            message = " ".join(context.args[1:])
            user = get_user_by_username(username)
            if user:
                await context.bot.send_message(chat_id=user['id'], text=message)
                await update.message.reply_text(f"Сообщение отправлено пользователю @{username}.")
            else:
                await update.message.reply_text(f"Пользователь @{username} не найден.")
        else:
            await update.message.reply_text("Пожалуйста, укажите username пользователя и сообщение для отправки.")

async def broadcast_message_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id == 929527704:
        if context.args:
            message = " ".join(context.args)
            users = get_all_users()
            for user in users:
                if not is_user_blocked(user['id']):
                    try:
                        await context.bot.send_message(chat_id=user['id'], text=message)
                    except Exception as e:
                        logger.error(f"Не удалось отправить сообщение пользователю {user['id']}: {e}")
            await update.message.reply_text("Сообщение отправлено всем пользователям.")
        else:
            await update.message.reply_text("Пожалуйста, укажите сообщение для рассылки.")
