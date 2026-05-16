import subprocess, os, asyncio
from telegram import Update
from telegram.ext import Application, MessageHandler, CommandHandler, filters, ContextTypes

BOT_TOKEN = "8856774127:AAEK3DGvBwR1HK5ozsdJHSHnWl-pbHw3K4c"
ALLOWED = [6377777497, 1088494994]

def check(update): return update.effective_user.id in ALLOWED

async def cmd_start(update, context):
    if not check(update): return
    await update.message.reply_text("✅ Claude ассистент готов. Пишите вопросы.")

async def cmd_status(update, context):
    if not check(update): return
    await update.message.reply_text("✅ Активен | Claude Code")

async def cmd_new(update, context):
    if not check(update): return
    context.user_data.clear()
    await update.message.reply_text("🔄 Новый диалог начат.")

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check(update): return
    text = update.message.text
    await update.message.reply_text("⏳ Думаю...")
    try:
        result = subprocess.run(
            ["claude", "-p", text, "--output-format", "text"],
            capture_output=True, text=True, timeout=120
        )
        reply = result.stdout.strip() or result.stderr.strip() or "Нет ответа"
    except subprocess.TimeoutExpired:
        reply = "⏱ Слишком долго, попробуйте короче."
    except Exception as e:
        reply = f"❌ Ошибка: {e}"
    for i in range(0, len(reply), 4096):
        await update.message.reply_text(reply[i:i+4096])

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("new", cmd_new))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
    print("Bot running...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
