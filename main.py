import logging
from io import BytesIO
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from youtube_audio_downloader import download_audio, start
from user_manager import add_user_command, remove_user_command, list_users_command, block_user_command, unblock_user_command, send_message_command, broadcast_message_command
from gpt_chat import register_handlers as register_gpt_handlers, CHAT_CONTEXT, get_gpt_response, end_chat_due_to_inactivity, generate_image
from user_database import get_user_by_id, increment_request_count, check_and_reset_request_counts, add_column_if_not_exists, add_user

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TOKEN = '7250364439:AAEo9bXrJJ9eQwXF3WVf3-BqoprsE5Te-F4'
AUTHORIZED_USER_ID = 929527704

image_prompt_context = {}

def main() -> None:
    add_column_if_not_exists()

    application = Application.builder().token(TOKEN).build()

    job_queue = application.job_queue

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("adduser", add_user_command))
    application.add_handler(CommandHandler("removeuser", remove_user_command))
    application.add_handler(CommandHandler("listusers", list_users_command))
    application.add_handler(CommandHandler("blockuser", block_user_command))
    application.add_handler(CommandHandler("unblockuser", unblock_user_command))
    application.add_handler(CommandHandler("sendmessage", send_message_command))
    application.add_handler(CommandHandler("broadcast", broadcast_message_command))
    application.add_handler(CommandHandler("admincommands", admin_commands))
    application.add_handler(CommandHandler("generateimage", initiate_generate_image))
    application.add_handler(CommandHandler("commands", user_commands))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    register_gpt_handlers(application)

    application.run_polling()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user = get_user_by_id(user_id)

    if not user:
        nickname = update.message.from_user.full_name
        username = update.message.from_user.username
        add_user(user_id, nickname, username)
        await update.message.reply_text("Добро пожаловать! Вы успешно авторизованы. Теперь вы можете пользоваться ботом.")
    else:
        await update.message.reply_text("Вы уже авторизованы и можете пользоваться ботом.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user = get_user_by_id(user_id)

    if not user:
        nickname = update.message.from_user.full_name
        await update.message.reply_text(f'{nickname}, к сожалению, вы ещё не авторизованы. Нажмите /start для пользования ботом, спасибо!')
        return

    if user_id in CHAT_CONTEXT:
        await handle_chat_message(update, context)
    elif user_id in image_prompt_context:
        prompt = update.message.text
        await generate_image_command(update, context, prompt)
        del image_prompt_context[user_id]
    else:
        text = update.message.text

        if user_id == AUTHORIZED_USER_ID and text.startswith("Message[") and text.endswith("]"):
            message_to_send = text[len("Message["):-1]
            await broadcast_message(context, message_to_send)
        else:
            check_and_reset_request_counts()
            increment_request_count(user_id)
            await download_audio(update, context)

async def handle_chat_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    message_text = update.message.text
    CHAT_CONTEXT[user_id]['messages'].append({'role': 'user', 'content': message_text})
    
    response = await get_gpt_response(user_id)
    await update.message.reply_text(response)

    if 'timeout' in CHAT_CONTEXT[user_id] and CHAT_CONTEXT[user_id]['timeout']:
        context.job_queue.scheduler.remove_job(CHAT_CONTEXT[user_id]['timeout'].id)
    CHAT_CONTEXT[user_id]['timeout'] = context.job_queue.run_once(end_chat_due_to_inactivity, 3600, data=user_id)

async def end_chat_due_to_inactivity(context: ContextTypes.DEFAULT_TYPE):
    user_id = context.job.data
    if user_id in CHAT_CONTEXT:
        del CHAT_CONTEXT[user_id]
        await context.bot.send_message(chat_id=user_id, text="Чат завершен из-за неактивности.", disable_notification=True)

async def admin_commands(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id == AUTHORIZED_USER_ID:
        commands = """
        /adduser <user_id> <nickname> <username> - Добавить пользователя
        /removeuser <user_id> - Удалить пользователя
        /listusers - Список пользователей
        /blockuser <user_id> - Заблокировать пользователя
        /unblockuser <user_id> - Разблокировать пользователя
        /sendmessage <username> <message> - Отправить сообщение пользователю
        /broadcast <message> - Отправить сообщение всем пользователям
        /chat - Начать чат с GPT-4
        /endchat - Завершить чат с GPT-4
        /generateimage - Начать процесс генерации изображения
        """
        await update.message.reply_text(commands)
    else:
        await update.message.reply_text("Эта команда доступна только администратору.")

async def user_commands(update: Update, context: ContextTypes.DEFAULT_TYPE):
    commands = """
    Доступные команды для пользователей:
    /start - Начало работы с ботом
    /chat - Начать чат с GPT-4
    /endchat - Завершить чат с GPT-4
    /generateimage - Начать процесс генерации изображения
    Вы также можете отправить ссылку на YouTube видео для загрузки аудио.
    """
    await update.message.reply_text(commands)

async def initiate_generate_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id == AUTHORIZED_USER_ID:
        image_prompt_context[user_id] = True
        await update.message.reply_text("Пожалуйста, опишите, что вы хотите сгенерировать.")
    else:
        await update.message.reply_text("Эта команда доступна только администратору.")

async def generate_image_command(update: Update, context: ContextTypes.DEFAULT_TYPE, prompt: str):
    user_id = update.message.from_user.id
    image = await generate_image(prompt)
    if image:
        with BytesIO() as output:
            image.save(output, format="PNG")
            output.seek(0)
            await context.bot.send_photo(chat_id=update.message.chat_id, photo=output)
    else:
        await update.message.reply_text("Произошла ошибка при генерации изображения.")

async def broadcast_message(context, message):
    """Функция для рассылки сообщения всем пользователям."""
    from user_manager import get_all_users, is_user_blocked
    users = get_all_users()
    for user in users:
        if not is_user_blocked(user['id']):
            try:
                await context.bot.send_message(chat_id=user['id'], text=message)
            except Exception as e:
                logger.error(f"Не удалось отправить сообщение пользователю {user['id']}: {e}")

if __name__ == '__main__':
    main()
