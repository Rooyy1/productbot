import os
import json
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes
)
from course_bot import user_progress_db, LESSONS, UserProgress

class AdminBot:
    def __init__(self, token: str, admin_ids: list):
        self.application = Application.builder().token(token).build()
        self.admin_ids = admin_ids
        self.setup_handlers()
    
    async def check_admin(self, update: Update) -> bool:
        """Проверка прав администратора"""
        return update.effective_user.id in self.admin_ids
    
    def setup_handlers(self):
        """Настройка обработчиков"""
        self.application.add_handler(CommandHandler("admin", self.admin_panel))
        self.application.add_handler(CallbackQueryHandler(self.admin_button_handler))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_admin_message))
    
    async def admin_panel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Панель администратора"""
        if not await self.check_admin(update):
            await update.message.reply_text("⛔ Доступ запрещен")
            return
        
        stats = self.get_stats()
        
        message = f"""
👑 *Панель администратора*

📊 **Статистика курса:**
• Всего пользователей: {stats['total_users']}
• Активных: {stats['active_users']}
• Завершивших: {stats['completed_users']}

📚 **Прогресс по урокам:**
{self.format_lesson_stats(stats['lesson_stats'])}

📝 **Задания:**
• Сдано: {stats['submitted_assignments']}
• Проверено: {stats['checked_assignments']}
        """
        
        keyboard = [
            [InlineKeyboardButton("👥 Список пользователей", callback_data="admin_users")],
            [InlineKeyboardButton("📊 Детальная статистика", callback_data="admin_stats")],
            [InlineKeyboardButton("📝 Проверить задания", callback_data="admin_check")],
            [InlineKeyboardButton("📢 Рассылка", callback_data="admin_broadcast")]
        ]
        
        await update.message.reply_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    def get_stats(self) -> dict:
        """Получить статистику"""
        stats = {
            'total_users': len(user_progress_db),
            'active_users': 0,
            'completed_users': 0,
            'lesson_stats': {},
            'submitted_assignments': 0,
            'checked_assignments': 0
        }
        
        for progress in user_progress_db.values():
            if progress.status.value == 'in_progress':
                stats['active_users'] += 1
            elif progress.status.value == 'completed':
                stats['completed_users'] += 1
            
            stats['submitted_assignments'] += len(progress.submitted_assignments)
            stats['checked_assignments'] += sum(1 for checked in progress.checked_assignments.values() if checked)
            
            for lesson_id in progress.completed_lessons:
                stats['lesson_stats'][lesson_id] = stats['lesson_stats'].get(lesson_id, 0) + 1
        
        return stats
    
    def format_lesson_stats(self, lesson_stats: dict) -> str:
        """Форматировать статистику по урокам"""
        result = []
        for i in range(1, len(LESSONS) + 1):
            count = lesson_stats.get(i, 0)
            percentage = (count / len(user_progress_db) * 100) if user_progress_db else 0
            result.append(f"Урок {i}: {count} ({percentage:.1f}%)")
        return "\n".join(result)
    
    async def admin_button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик кнопок админки"""
        query = update.callback_query
        await query.answer()
        
        if not await self.check_admin(update):
            return
        
        data = query.data
        
        if data == "admin_users":
            await self.show_users_list(update, context)
        elif data == "admin_stats":
            await self.show_detailed_stats(update, context)
        elif data.startswith("admin_user_"):
            user_id = int(data.split("_")[2])
            await self.show_user_details(update, context, user_id)
    
    async def show_users_list(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать список пользователей"""
        users_list = []
        for user_id, progress in list(user_progress_db.items())[:50]:  # Первые 50 пользователей
            users_list.append(f"👤 ID: {user_id} | Прогресс: {len(progress.completed_lessons)}/{len(LESSONS)}")
        
        message = "👥 *Список пользователей:*\n\n" + "\n".join(users_list)
        
        keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data="admin_back")]]
        
        await update.callback_query.edit_message_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def handle_admin_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка сообщений администратора"""
        if not await self.check_admin(update):
            return
        
        # Здесь можно добавить логику для обработки команд администратора
        pass

def main():
    """Запуск админ-бота"""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    admin_ids = [123456789]  # Замените на ваш ID администратора
    
    if not token:
        print("TELEGRAM_BOT_TOKEN не найден")
        return
    
    bot = AdminBot(token, admin_ids)
    print("Админ-бот запущен...")
    bot.application.run_polling()

if __name__ == "__main__":
    main()