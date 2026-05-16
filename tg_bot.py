import subprocess, json, re, os
from pathlib import Path
from telegram import Update
from telegram.ext import Application, MessageHandler, CommandHandler, filters, ContextTypes

BOT_TOKEN = "8856774127:AAEK3DGvBwR1HK5ozsdJHSHnWl-pbHw3K4c"
ALLOWED   = [6377777497, 1088494994]

MEMORY_DIR = Path("/root/agent-memory");   MEMORY_DIR.mkdir(exist_ok=True)
HISTORY_MAX = 20  # сколько сообщений помнит в диалоге

SYSTEM = """Ты — персональный AI-ассистент. Умный, практичный, без воды.

# Что ты знаешь о пользователе:
{facts}

# Правила:
1. Отвечай коротко и по делу.
2. Если узнал важный факт о пользователе — добавь в ответ тег [MEMORY: факт].
3. Для сложных задач — сначала план, потом выполнение.
4. Если задача неясна — задай 1-2 уточняющих вопроса."""

# ── persistence ──────────────────────────────────────────────────────────────

def load(uid):
    f = MEMORY_DIR / f"{uid}.json"
    return json.loads(f.read_text()) if f.exists() else {"facts": [], "history": []}

def save(uid, data):
    (MEMORY_DIR / f"{uid}.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2))

# ── claude call ───────────────────────────────────────────────────────────────

def ask_claude(text, data):
    facts = "\n".join(f"- {f}" for f in data["facts"]) or "Пока ничего."
    system = SYSTEM.format(facts=facts)

    history_str = ""
    for m in data["history"][-HISTORY_MAX:]:
        role = "Пользователь" if m["role"] == "user" else "Ассистент"
        history_str += f"{role}: {m['content']}\n"

    prompt = f"{system}\n\n---\n{history_str}Пользователь: {text}\nАссистент:"

    r = subprocess.run(
    ["claude", "-p", prompt,
     "--output-format", "text",
     "--dangerously-skip-permissions"],
    capture_output=True, text=True, timeout=120, cwd="/root"
    )
    return (r.stdout or r.stderr).strip()

def process_memory(uid, data, response):
    """Извлекаем [MEMORY: ...] теги, сохраняем факты."""
    tags  = re.findall(r'\[MEMORY:\s*(.+?)\]', response)
    clean = re.sub(r'\[MEMORY:\s*.+?\]\n?', '', response).strip()
    if tags:
        data["facts"].extend(tags)
        data["facts"] = list(dict.fromkeys(data["facts"]))  # убрать дубли
    return clean

# ── handlers ──────────────────────────────────────────────────────────────────

def guard(uid): return uid in ALLOWED

async def cmd_start(u: Update, _):
    if not guard(u.effective_user.id): return
    await u.message.reply_text(
        "👋 Привет! Я ваш персональный ассистент.\n\n"
        "Команды:\n"
        "/new — новый диалог (память сохраняется)\n"
        "/memory — что я о вас помню\n"
        "/forget — забыть всё\n"
        "/history — последние 5 сообщений")

async def cmd_new(u: Update, _):
    if not guard(u.effective_user.id): return
    data = load(u.effective_user.id)
    data["history"] = []
    save(u.effective_user.id, data)
    await u.message.reply_text("🔄 Диалог сброшен. Память сохранена.")

async def cmd_status(u: Update, _):
    if not guard(u.effective_user.id): return
    await u.message.reply_text("✅ Агент активен | Claude Code")

async def cmd_memory(u: Update, _):
    if not guard(u.effective_user.id): return
    data = load(u.effective_user.id)
    facts = data.get("facts", [])
    if facts:
        text = "🧠 Что я о вас знаю:\n" + "\n".join(f"• {f}" for f in facts)
    else:
        text = "🧠 Пока ничего не запомнил."
    await u.message.reply_text(text)

async def cmd_forget(u: Update, _):
    if not guard(u.effective_user.id): return
    save(u.effective_user.id, {"facts": [], "history": []})
    await u.message.reply_text("🗑 Память и история очищены.")

async def cmd_history(u: Update, _):
    if not guard(u.effective_user.id): return
    data = load(u.effective_user.id)
    msgs = data["history"][-5:]
    if not msgs:
        await u.message.reply_text("История пуста."); return
    lines = []
    for m in msgs:
        role = "👤" if m["role"] == "user" else "🤖"
        lines.append(f"{role} {m['content'][:200]}")
    await u.message.reply_text("\n\n".join(lines))

async def handle(u: Update, _):
    uid = u.effective_user.id
    if not guard(uid): return
    text = u.message.text

    wait = await u.message.reply_text("⏳ Думаю...")
    data = load(uid)

    try:
        response = ask_claude(text, data)
        clean    = process_memory(uid, data, response)

        # Сохраняем историю
        data["history"].append({"role": "user",      "content": text})
        data["history"].append({"role": "assistant",  "content": clean})
        save(uid, data)

        await wait.delete()
        for i in range(0, max(len(clean), 1), 4096):
            await u.message.reply_text(clean[i:i+4096] or "✅ Готово")

    except subprocess.TimeoutExpired:
        await wait.edit_text("⏱ Слишком долго — попробуйте покороче.")
    except Exception as e:
        await wait.edit_text(f"❌ Ошибка: {e}")

# ── main ──────────────────────────────────────────────────────────────────────

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start",   cmd_start))
    app.add_handler(CommandHandler("new",     cmd_new))
    app.add_handler(CommandHandler("status",  cmd_status))
    app.add_handler(CommandHandler("memory",  cmd_memory))
    app.add_handler(CommandHandler("forget",  cmd_forget))
    app.add_handler(CommandHandler("history", cmd_history))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
    print("Agent running...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()