import openai
import logging
import requests
from telegram import Update
from telegram.ext import CommandHandler, MessageHandler, filters, ContextTypes, CallbackContext
from io import BytesIO
from PIL import Image
from user_manager import is_user_blocked
from user_database import get_user_by_id, increment_request_count, check_and_reset_request_counts

OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
openai.api_key = OPENAI_API_KEY

logger = logging.getLogger(__name__)
CHAT_CONTEXT = {}

async def start_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if not is_user_blocked(user_id):
        CHAT_CONTEXT[user_id] = {'messages': [], 'timeout': None}
        await update.message.reply_text("Начался чат с GPT-4. Можете отправлять свои сообщения. Напишите /endchat чтобы завершить чат.")

    user = get_user_by_id(user_id)
    if not user:
        nickname = update.message.from_user.full_name
        await update.message.reply_text(f'{nickname}, к сожалению, вы ещё не авторизованы. Нажмите /start для пользования ботом, спасибо!')
        return

async def end_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if not is_user_blocked(user_id):
        if user_id in CHAT_CONTEXT:
            del CHAT_CONTEXT[user_id]
            await update.message.reply_text("Чат завершен.")
        else:
            await update.message.reply_text("У вас нет активного чата.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id not in CHAT_CONTEXT:
        await update.message.reply_text("Для начала чата используйте команду /chat.")
        return

    message_text = update.message.text
    CHAT_CONTEXT[user_id]['messages'].append({'role': 'user', 'content': message_text})
    
    response = await get_gpt_response(user_id)
    await update.message.reply_text(response)

    if 'timeout' in CHAT_CONTEXT[user_id] and CHAT_CONTEXT[user_id]['timeout']:
        context.job_queue.scheduler.remove_job(CHAT_CONTEXT[user_id]['timeout'].id)
    CHAT_CONTEXT[user_id]['timeout'] = context.job_queue.run_once(end_chat_due_to_inactivity, 3600, data=user_id)

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id not in CHAT_CONTEXT:
        await update.message.reply_text("Для начала чата используйте команду /chat.")
        return

    file = await update.message.photo[-1].get_file()
    file_path = f"{file.file_id}.jpg"
    await file.download_to_drive(file_path)

    if 'timeout' in CHAT_CONTEXT[user_id] and CHAT_CONTEXT[user_id]['timeout']:
        context.job_queue.scheduler.remove_job(CHAT_CONTEXT[user_id]['timeout'].id)
    CHAT_CONTEXT[user_id]['timeout'] = context.job_queue.run_once(end_chat_due_to_inactivity, 3600, data=user_id)

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id not in CHAT_CONTEXT:
        await update.message.reply_text("Для начала чата используйте команду /chat.")
        return

    file = await update.message.document.get_file()
    file_path = f"{file.file_id}.{file.file_path.split('.')[-1]}"
    await file.download_to_drive(file_path)
    
    response = await analyze_image(file_path)
    await update.message.reply_text(response)

    if 'timeout' in CHAT_CONTEXT[user_id] and CHAT_CONTEXT[user_id]['timeout']:
        context.job_queue.scheduler.remove_job(CHAT_CONTEXT[user_id]['timeout'].id)
    CHAT_CONTEXT[user_id]['timeout'] = context.job_queue.run_once(end_chat_due_to_inactivity, 3600, data=user_id)

async def get_gpt_response(user_id):
    messages = CHAT_CONTEXT[user_id]['messages']
    check_and_reset_request_counts()
    increment_request_count(user_id)
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=messages
        )
        gpt_message = response['choices'][0]['message']['content']
        CHAT_CONTEXT[user_id]['messages'].append({'role': 'assistant', 'content': gpt_message})
        return gpt_message
    except Exception as e:
        logger.error(f"Error getting response from GPT-4: {e}")
        return "Произошла ошибка при получении ответа от GPT-4."

async def analyze_image(file_path):
    return f"Изображение {file_path} проанализировано."

async def generate_image(prompt):
    try:
        response = openai.Image.create(
            prompt=prompt,
            n=1,
            size="1024x1024"
        )
        image_url = response['data'][0]['url']
        image_response = requests.get(image_url)
        image = Image.open(BytesIO(image_response.content))
        return image
    except Exception as e:
        logger.error(f"Error generating image: {e}")
        return None

async def end_chat_due_to_inactivity(context: CallbackContext):
    user_id = context.job.data
    if user_id in CHAT_CONTEXT:
        del CHAT_CONTEXT[user_id]
        await context.bot.send_message(chat_id=user_id, text="Чат завершен из-за неактивности.", disable_notification=True)
    
def register_handlers(application):
    application.add_handler(CommandHandler("chat", start_chat))
    application.add_handler(CommandHandler("endchat", end_chat))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
