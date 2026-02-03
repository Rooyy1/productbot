import os
import json
import logging
import asyncio
from datetime import datetime
from typing import Dict, List, Optional
from enum import Enum
from dataclasses import dataclass, asdict
from dotenv import load_dotenv

from telegram import (
    InlineKeyboardMarkup, 
    InlineKeyboardButton, 
    Update,
    Bot
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes
)

import sys

# Загрузка переменных окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Получаем URL для webhook из переменных окружения
RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL")
WEBHOOK_URL = f"{RENDER_EXTERNAL_URL}/webhook" if RENDER_EXTERNAL_URL else None
PORT = int(os.environ.get("PORT", 10000))
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Проверяем токен
if not BOT_TOKEN:
    logger.error("TELEGRAM_BOT_TOKEN не найден в .env файле")
    sys.exit(1)

# Структуры данных
class UserStatus(Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"

class AssignmentStatus(Enum):
    NOT_SUBMITTED = "not_submitted"
    SUBMITTED = "submitted"
    CHECKED = "checked"

@dataclass
class UserProgress:
    user_id: int
    current_lesson: int = 1
    completed_lessons: List[int] = None
    submitted_assignments: Dict[int, str] = None  # lesson_id: answer
    checked_assignments: Dict[int, bool] = None  # lesson_id: is_checked
    status: UserStatus = UserStatus.NOT_STARTED
    
    def __post_init__(self):
        if self.completed_lessons is None:
            self.completed_lessons = []
        if self.submitted_assignments is None:
            self.submitted_assignments = {}
        if self.checked_assignments is None:
            self.checked_assignments = {}

@dataclass
class Lesson:
    id: int
    title: str
    description: str
    video_url: Optional[str] = None
    text_content: Optional[str] = None
    assignment_question: Optional[str] = None
    assignment_hint: Optional[str] = None

# Данные курса про Александра Чижова
COURSE_TITLE = "Курс 'Методы анализа от Александра Чижова'"
COURSE_DESCRIPTION = """
🎓 Этот курс основан на методиках Александра Чижова - эксперта в области аналитики и принятия решений.

📚 Что вы узнаете:
• Методы системного анализа
• Принятие решений в условиях неопределенности
• Аналитические инструменты для бизнеса
• Практические кейсы от Александра

⏰ Длительность: 14 дней
📊 Уровень: от начинающего до продвинутого
"""

LESSONS = [
    Lesson(
        id=1,
        title="Введение в аналитическое мышление",
        description="Основные принципы аналитического подхода по методу Александра Чижова",
        text_content="""
📖 **Урок 1: Введение в аналитическое мышление**

Александр Чижов подчеркивает, что аналитическое мышление - это не просто набор инструментов, а система восприятия реальности.

**Ключевые принципы:**
1. **Системность** - любой объект рассматривается как часть системы
2. **Многофакторность** - учет всех возможных влияющих факторов
3. **Динамичность** - анализ изменений во времени
4. **Практичность** - каждый анализ должен приводить к конкретным действиям

**Мысли Александра:**
> "Анализ без действия - это просто философия. Действие без анализа - это авантюра."

**Пример из практики:**
Как Александр помог компании увеличить прибыль на 30% через анализ клиентских путей.
        """,
        video_url="https://example.com/video1.mp4",
        assignment_question="Опишите проблему в вашей работе/бизнесе, которую можно решить аналитическим подходом. Какие факторы нужно учесть?",
        assignment_hint="Попробуйте разбить проблему на составляющие части"
    ),
    Lesson(
        id=2,
        title="Системный анализ",
        description="Как видеть целое через части и связи между ними",
        text_content="""
📖 **Урок 2: Системный анализ по методу Чижова**

Александр учит, что мир состоит не из объектов, а из связей между ними.

**Методология:**
1. **Выделение элементов системы**
2. **Определение связей и взаимовлияний**
3. **Анализ входов и выходов**
4. **Поиск точек воздействия**

**Инструменты:**
• Диаграммы влияния
• Карты стейкхолдеров
• Модели потоков

**Кейс Александра:**
Как системный анализ помог оптимизировать логистическую цепочку и сократить издержки на 45%.
        """,
        video_url="https://example.com/video2.mp4",
        assignment_question="Нарисуйте схему любой системы, с которой вы работаете (бизнес-процесс, проект и т.д.). Покажите основные элементы и связи.",
        assignment_hint="Начните с определения границ системы"
    ),
    Lesson(
        id=3,
        title="Принятие решений в неопределенности",
        description="Методы работы с рисками и неполными данными",
        text_content="""
📖 **Урок 3: Решения в условиях неопределенности**

По словам Александра, "неопределенность - это не проблема, а условие работы".

**Подходы:**
1. **Сценарное планирование**
2. **Анализ чувствительности**
3. **Метод экспертных оценок**
4. **Байесовское обновление**

**Принцип Чижова:**
> "Принимайте решения на основе лучшей доступной информации, но всегда имейте план Б, В и Г."

**Практический пример:**
Как Александр помог стартапу принять решение о выходе на новый рынок в условиях пандемии.
        """,
        video_url="https://example.com/video3.mp4",
        assignment_question="Опишите решение, которое вам нужно принять. Какие факторы неопределенности существуют? Как можно их уменьшить?",
        assignment_hint='Составьте таблицу "что если" для разных сценариев'
    ),
    Lesson(
        id=4,
        title="Аналитические инструменты",
        description="Практические инструменты для ежедневной работы",
        text_content="""
📖 **Урок 4: Инструментарий аналитика**

Александр собрал уникальную коллекцию инструментов, которые действительно работают.

**Основные инструменты:**
1. **PESTLE-анализ** для макросреды
2. **SWOT-анализ 2.0** с динамическими факторами
3. **Модель пяти сил Портера** с цифровыми корректировками
4. **Матрица Эйзенхауэра** для приоритизации

**Совет Александра:**
> "Не используйте инструменты шаблонно. Адаптируйте их под свою конкретную задачу."

**Результаты:**
Компании, работающие с Александром, в среднем улучшают KPI на 25-40% после внедрения этих инструментов.
        """,
        video_url="https://example.com/video4.mp4",
        assignment_question="Примените один из аналитических инструментов к вашему проекту. Что нового вы узнали?",
        assignment_hint="Начните с самого простого - SWOT анализа"
    ),
    Lesson(
        id=5,
        title="Завершение и внедрение",
        description="Как превратить анализ в конкретные действия и результаты",
        text_content="""
📖 **Урок 5: От анализа к действию**

Финальный этап, на котором, по мнению Александра, "происходит магия".

**Алгоритм внедрения:**
1. **Формулировка конкретных действий**
2. **Назначение ответственных**
3. **Определение сроков и контрольных точек**
4. **Система мониторинга результатов**

**Заключительные слова Александра:**
> "Анализ - это начало пути. Настоящая ценность создается только действиями. Начните с малого, но начните сегодня."

**Успешные кейсы:**
Истории 5 компаний, которые благодаря этим методикам достигли прорывных результатов.
        """,
        video_url="https://example.com/video5.mp4",
        assignment_question="Составьте план внедрения одного изменения на основе пройденного курса. Что вы сделаете в первую очередь?",
        assignment_hint="Разбейте план на конкретные шаги с датами"
    )
]

# Хранилище данных пользователей
user_progress_db: Dict[int, UserProgress] = {}

class CourseBot:
    def __init__(self):
        self.application = None
        
    def create_application(self):
        """Создание приложения с обработчиками"""
        # Создаем приложение
        self.application = Application.builder().token(BOT_TOKEN).build()
        
        # Настраиваем обработчики
        self.setup_handlers()
    
    def setup_handlers(self):
        """Настройка обработчиков"""
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("progress", self.progress_command))
        self.application.add_handler(CommandHandler("menu", self.main_menu))
        
        # Исправляем регулярное выражение
        self.application.add_handler(CallbackQueryHandler(
            self.button_handler,
            pattern=r"^(start_course|main_menu|lesson_\d+|submit_\d+|next_lesson|prev_lesson|check_\d+|back_to_lesson|complete_lesson_\d+|assignment_\d+|profile|about_course|about_author|feedback)$"
        ))
        
        self.application.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            self.handle_assignment_submission
        ))
        
        # Добавляем обработчик ошибок
        self.application.add_error_handler(self.error_handler)
    
    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик ошибок"""
        logger.error(f"Update {update} caused error {context.error}")
        
        if update and update.effective_user:
            try:
                error_message = f"⚠️ Произошла ошибка. Пожалуйста, попробуйте еще раз или нажмите /start"
                await context.bot.send_message(
                    chat_id=update.effective_user.id,
                    text=error_message
                )
            except:
                pass
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start"""
        user = update.effective_user
        
        if user.id not in user_progress_db:
            user_progress_db[user.id] = UserProgress(user_id=user.id)
        
        welcome_message = f"""
👋 Привет, {user.first_name}!

{COURSE_DESCRIPTION}

Автор курса: **Александр Чижов**
• Эксперт в системном анализе
• Более 15 лет практического опыта
• Консультант Fortune 500 компаний
• Автор методики "Практический анализ"

Готовы начать обучение?
        """
        
        keyboard = [
            [InlineKeyboardButton("🚀 Начать курс", callback_data="start_course")],
            [InlineKeyboardButton("📊 Мой прогресс", callback_data="profile")],
            [InlineKeyboardButton("ℹ️ О курсе", callback_data="about_course")]
        ]
        
        await update.message.reply_text(
            welcome_message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def main_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Главное меню"""
        user = update.effective_user
        
        keyboard = [
            [InlineKeyboardButton("📚 Продолжить обучение", callback_data=f"lesson_1")],
            [InlineKeyboardButton("📊 Мой прогресс", callback_data="profile")],
            [InlineKeyboardButton("🏆 Домашние задания", callback_data="assignment_1")],
            [InlineKeyboardButton("👨‍🏫 Об авторе", callback_data="about_author")]
        ]
        
        message_text = "🏠 *Главное меню курса*\nВыберите действие:"
        
        # Проверяем, откуда пришел запрос
        if update.callback_query:
            # Если из callback (кнопки)
            await update.callback_query.edit_message_text(
                message_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        elif update.message:
            # Если из команды /menu
            await update.message.reply_text(
                message_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        else:
            # Если из другого источника, отправляем новое сообщение
            await context.bot.send_message(
                chat_id=user.id,
                text=message_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
    
    async def progress_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать прогресс"""
        await self.show_progress(update, context)
    
    async def show_progress(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать прогресс пользователя"""
        user = update.effective_user
        progress = user_progress_db.get(user.id, UserProgress(user_id=user.id))
        
        completed = len(progress.completed_lessons)
        total = len(LESSONS)
        percentage = (completed / total * 100) if total > 0 else 0
        
        submitted = len(progress.submitted_assignments)
        checked = sum(1 for checked in progress.checked_assignments.values() if checked)
        
        progress_text = f"""
📊 *Ваш прогресс*

🎯 **Прогресс по курсу:**
{self._create_progress_bar(percentage)} {percentage:.1f}%
✅ Пройдено уроков: {completed}/{total}

📝 **Домашние задания:**
📤 Сдано: {submitted}/{total}
✅ Проверено: {checked}/{total}

🏆 **Текущий статус:** {progress.status.value.replace('_', ' ').title()}
📖 **Текущий урок:** {progress.current_lesson}/{total}

💡 *Продолжайте в том же духе! Каждый урок приближает вас к результату.*
        """
        
        keyboard = [
            [InlineKeyboardButton("📚 Продолжить обучение", callback_data=f"lesson_{progress.current_lesson}")],
            [InlineKeyboardButton("📝 Мои задания", callback_data=f"assignment_{progress.current_lesson}")],
            [InlineKeyboardButton("🏠 В главное меню", callback_data="main_menu")]
        ]
        
        if update.callback_query:
            await update.callback_query.edit_message_text(
                progress_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        elif update.message:
            await update.message.reply_text(
                progress_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
    
    def _create_progress_bar(self, percentage: float) -> str:
        """Создать текстовый прогресс-бар"""
        bars = 10
        filled = int(percentage / 100 * bars)
        return "█" * filled + "░" * (bars - filled)
    
    async def show_lesson(self, update: Update, context: ContextTypes.DEFAULT_TYPE, lesson_id: int):
        """Показать урок"""
        user = update.effective_user
        progress = user_progress_db.get(user.id, UserProgress(user_id=user.id))
        
        if lesson_id < 1 or lesson_id > len(LESSONS):
            await update.callback_query.answer("Урок не найден")
            return
        
        lesson = LESSONS[lesson_id - 1]
        progress.current_lesson = lesson_id
        user_progress_db[user.id] = progress
        
        # Формируем сообщение урока
        lesson_message = f"""
📖 *Урок {lesson_id}: {lesson.title}*

{lesson.text_content}

🎬 *Видео-материал:* {lesson.video_url if lesson.video_url else "Скоро будет добавлено"}
        """
        
        # Создаем клавиатуру
        keyboard = []
        
        if lesson.assignment_question:
            keyboard.append([InlineKeyboardButton(
                "📝 Домашнее задание", 
                callback_data=f"submit_{lesson_id}"
            )])
        
        # Кнопки навигации
        nav_buttons = []
        if lesson_id > 1:
            nav_buttons.append(InlineKeyboardButton(
                "◀️ Предыдущий", 
                callback_data=f"lesson_{lesson_id - 1}"
            ))
        
        if lesson_id < len(LESSONS):
            nav_buttons.append(InlineKeyboardButton(
                "Следующий ▶️", 
                callback_data=f"lesson_{lesson_id + 1}"
            ))
        
        if nav_buttons:
            keyboard.append(nav_buttons)
        
        keyboard.extend([
            [InlineKeyboardButton("✅ Отметить как пройденный", callback_data=f"complete_lesson_{lesson_id}")],
            [InlineKeyboardButton("📊 Мой прогресс", callback_data="profile")],
            [InlineKeyboardButton("🏠 В главное меню", callback_data="main_menu")]
        ])
        
        # Отправляем или редактируем сообщение
        if update.callback_query:
            await update.callback_query.edit_message_text(
                lesson_message,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        else:
            await context.bot.send_message(
                chat_id=user.id,
                text=lesson_message,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
    
    async def show_assignment(self, update: Update, context: ContextTypes.DEFAULT_TYPE, lesson_id: int):
        """Показать домашнее задание"""
        user = update.effective_user
        progress = user_progress_db.get(user.id, UserProgress(user_id=user.id))
        
        if lesson_id < 1 or lesson_id > len(LESSONS):
            await update.callback_query.answer("Урок не найден")
            return
        
        lesson = LESSONS[lesson_id - 1]
        
        if not lesson.assignment_question:
            await update.callback_query.answer("Для этого урока нет задания")
            return
        
        assignment_status = "❌ Не сдано"
        if str(lesson_id) in progress.submitted_assignments:
            assignment_status = "📤 Сдано (ожидает проверки)" if not progress.checked_assignments.get(str(lesson_id)) else "✅ Проверено"
        
        assignment_message = f"""
📝 *Домашнее задание к уроку {lesson_id}*

**Тема:** {lesson.title}

**Задание:**
{lesson.assignment_question}

💡 *Подсказка от Александра:*
{lesson.assignment_hint}

**Статус:** {assignment_status}
        """
        
        keyboard = []
        
        if str(lesson_id) not in progress.submitted_assignments:
            keyboard.append([InlineKeyboardButton(
                "📤 Сдать задание", 
                callback_data=f"submit_{lesson_id}"
            )])
        
        if str(lesson_id) in progress.submitted_assignments:
            keyboard.append([InlineKeyboardButton(
                "👀 Посмотреть мой ответ", 
                callback_data=f"check_{lesson_id}"
            )])
        
        keyboard.extend([
            [InlineKeyboardButton("📚 Вернуться к уроку", callback_data=f"lesson_{lesson_id}")],
            [InlineKeyboardButton("📊 Все задания", callback_data="assignment_1")],
            [InlineKeyboardButton("🏠 В главное меню", callback_data="main_menu")]
        ])
        
        await update.callback_query.edit_message_text(
            assignment_message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def handle_assignment_submission(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка сдачи домашнего задания"""
        user = update.effective_user
        
        # Проверяем, ожидаем ли мы ответ от пользователя
        if 'awaiting_submission' in context.user_data:
            lesson_id = context.user_data['awaiting_submission']
            progress = user_progress_db.get(user.id, UserProgress(user_id=user.id))
            
            # Сохраняем ответ
            progress.submitted_assignments[str(lesson_id)] = update.message.text
            progress.checked_assignments[str(lesson_id)] = False
            user_progress_db[user.id] = progress
            
            # Очищаем флаг ожидания
            del context.user_data['awaiting_submission']
            
            # Отправляем подтверждение
            confirmation_message = f"""
✅ *Ваше задание к уроку {lesson_id} принято!*

Александр или куратор проверят его в ближайшее время.

💡 *Совет от Александра:*
"Лучший способ научиться - это практика. Даже если ваш ответ не идеален, вы уже сделали важный шаг."

📊 Проверить статус всех заданий можно в разделе "Мой прогресс".
            """
            
            keyboard = [
                [InlineKeyboardButton("📚 Следующий урок", callback_data=f"lesson_{lesson_id + 1}")],
                [InlineKeyboardButton("📝 Посмотреть задание", callback_data=f"check_{lesson_id}")],
                [InlineKeyboardButton("📊 Мой прогресс", callback_data="profile")]
            ]
            
            await update.message.reply_text(
                confirmation_message,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
    
    async def show_submitted_assignment(self, update: Update, context: ContextTypes.DEFAULT_TYPE, lesson_id: int):
        """Показать сданное задание"""
        user = update.effective_user
        progress = user_progress_db.get(user.id, UserProgress(user_id=user.id))
        
        answer = progress.submitted_assignments.get(str(lesson_id), "")
        is_checked = progress.checked_assignments.get(str(lesson_id), False)
        
        if not answer:
            await update.callback_query.answer("Задание еще не сдано")
            return
        
        status = "✅ Проверено" if is_checked else "📤 Ожидает проверки"
        
        message = f"""
📝 *Ваш ответ к уроку {lesson_id}*

**Статус:** {status}

**Ваш ответ:**
{answer[:1500]}{'...' if len(answer) > 1500 else ''}
        """
        
        keyboard = [
            [InlineKeyboardButton("📚 Вернуться к уроку", callback_data=f"lesson_{lesson_id}")],
            [InlineKeyboardButton("📝 Все задания", callback_data="assignment_1")],
            [InlineKeyboardButton("🏠 В главное меню", callback_data="main_menu")]
        ]
        
        await update.callback_query.edit_message_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def complete_lesson(self, update: Update, context: ContextTypes.DEFAULT_TYPE, lesson_id: int):
        """Отметить урок как пройденный"""
        user = update.effective_user
        progress = user_progress_db.get(user.id, UserProgress(user_id=user.id))
        
        if lesson_id not in progress.completed_lessons:
            progress.completed_lessons.append(lesson_id)
            user_progress_db[user.id] = progress
        
        # Проверяем, завершен ли весь курс
        if len(progress.completed_lessons) == len(LESSONS):
            progress.status = UserStatus.COMPLETED
            
            completion_message = f"""
🏆 *Поздравляем, {user.first_name}!*

Вы успешно завершили курс "Методы анализа от Александра Чижова"!

🎯 **Ваши достижения:**
• Освоили {len(LESSONS)} ключевых методик
• Выполнили {len(progress.submitted_assignments)} практических заданий
• Приобрели навыки системного анализа

💪 **Слова Александра:**
> "Знание становится силой только тогда, когда применяется на практике. Вы сделали первый важный шаг. Продолжайте применять эти методы в своей работе!"

📚 **Что дальше?**
• Повторите сложные моменты
• Примените методики к реальным задачам
• Делитесь результатами с комьюнити

Сертификат о прохождении курса будет отправлен вам в течение 24 часов.
            """
            
            keyboard = [
                [InlineKeyboardButton("📊 Итоговый прогресс", callback_data="profile")],
                [InlineKeyboardButton("📝 Все задания", callback_data="assignment_1")],
                [InlineKeyboardButton("👨‍🏫 Оставить отзыв", callback_data="feedback")]
            ]
            
            await update.callback_query.edit_message_text(
                completion_message,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        else:
            await update.callback_query.answer(f"Урок {lesson_id} отмечен как пройденный! ✅")
            
            # Показываем следующий урок
            next_lesson = lesson_id + 1 if lesson_id < len(LESSONS) else lesson_id
            await self.show_lesson(update, context, next_lesson)
    
    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик inline-кнопок"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        
        if data == "start_course":
            user = query.from_user
            progress = user_progress_db.get(user.id, UserProgress(user_id=user.id))
            progress.status = UserStatus.IN_PROGRESS
            user_progress_db[user.id] = progress
            await self.show_lesson(update, context, 1)
        
        elif data == "main_menu":
            await self.main_menu(update, context)
        
        elif data == "profile":
            await self.show_progress(update, context)
        
        elif data.startswith("lesson_"):
            lesson_id = int(data.split("_")[1])
            await self.show_lesson(update, context, lesson_id)
        
        elif data.startswith("submit_"):
            lesson_id = int(data.split("_")[1])
            
            # Устанавливаем флаг, что ожидаем ответ от пользователя
            context.user_data['awaiting_submission'] = lesson_id
            
            lesson = LESSONS[lesson_id - 1]
            
            await query.edit_message_text(
                f"✍️ *Отправьте ваш ответ на задание:*\n\n{lesson.assignment_question}\n\n"
                f"💡 *Подсказка:* {lesson.assignment_hint}\n\n"
                "Просто напишите сообщение с вашим ответом в чат.",
                parse_mode='Markdown'
            )
        
        elif data.startswith("check_"):
            lesson_id = int(data.split("_")[1])
            await self.show_submitted_assignment(update, context, lesson_id)
        
        elif data.startswith("complete_lesson_"):
            lesson_id = int(data.split("_")[2])
            await self.complete_lesson(update, context, lesson_id)
        
        elif data.startswith("assignment_"):
            lesson_id = int(data.split("_")[1])
            await self.show_assignment(update, context, lesson_id)
        
        elif data == "about_course":
            await query.edit_message_text(
                COURSE_DESCRIPTION,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🚀 Начать обучение", callback_data="start_course")],
                    [InlineKeyboardButton("🏠 В главное меню", callback_data="main_menu")]
                ]),
                parse_mode='Markdown'
            )
        
        elif data == "about_author":
            author_info = """
👨‍🏫 *Александр Чижов*

**Профессиональный путь:**
• 15+ лет в аналитике и консалтинге
• Работал с компаниями из Fortune 500
• Основатель аналитического агентства "Системный подход"
• Автор книги "Практический анализ для бизнеса"

**Образование:**
• МГУ, факультет вычислительной математики
• MBA, Stanford Graduate School of Business
• Сертифицированный специалист по data science

**Философия:**
> "Сложное нужно делать простым, а простое - понятным. Анализ должен служить действию."

**Достижения:**
• Помог 200+ компаниям оптимизировать процессы
• Разработал уникальную методику системного анализа
• Провел 500+ консультаций и воркшопов
• Обучил более 5000 специалистов
            """
            
            await query.edit_message_text(
                author_info,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📚 Начать курс", callback_data="start_course")],
                    [InlineKeyboardButton("🏠 В главное меню", callback_data="main_menu")]
                ]),
                parse_mode='Markdown'
            )
        
        elif data == "feedback":
            await query.edit_message_text(
                "📝 *Оставьте отзыв о курсе*\n\n"
                "Ваше мнение очень важно для нас! Напишите, что понравилось, "
                "а что можно улучшить. Это поможет сделать курс еще лучше!\n\n"
                "Просто отправьте ваше сообщение с отзывом в чат.",
                parse_mode='Markdown'
            )

async def setup_webhook(bot: Bot):
    """Настройка webhook"""
    try:
        # Удаляем существующий webhook
        await bot.delete_webhook()
        
        # Устанавливаем новый webhook
        await bot.set_webhook(
            url=WEBHOOK_URL,
            drop_pending_updates=True
        )
        logger.info(f"Webhook установлен на {WEBHOOK_URL}")
        return True
    except Exception as e:
        logger.error(f"Ошибка при установке webhook: {e}")
        return False

async def run_webhook():
    """Запуск в режиме webhook"""
    logger.info(f"Запуск бота в режиме Webhook на порту {PORT}")
    logger.info(f"Webhook URL: {WEBHOOK_URL}")
    
    # Создаем бота
    bot_instance = CourseBot()
    bot_instance.create_application()
    
    # Настраиваем webhook
    success = await setup_webhook(bot_instance.application.bot)
    if not success:
        logger.error("Не удалось установить webhook")
        return
    
    # Запускаем webhook
    await bot_instance.application.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path="/webhook",
        webhook_url=WEBHOOK_URL
    )

async def run_polling():
    """Запуск в режиме polling"""
    logger.info("Запуск бота в режиме Polling...")
    
    # Создаем бота
    bot_instance = CourseBot()
    bot_instance.create_application()
    
    # Запускаем polling
    await bot_instance.application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True
    )

def main():
    """Основная функция запуска бота"""
    
    if not BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN не найден")
        return
    
    # Автоматически выбираем режим на основе наличия RENDER_EXTERNAL_URL
    if RENDER_EXTERNAL_URL and WEBHOOK_URL:
        logger.info("Обнаружен RENDER_EXTERNAL_URL, запускаю в режиме webhook")
        
        # Запускаем в режиме webhook
        try:
            asyncio.run(run_webhook())
        except KeyboardInterrupt:
            logger.info("Бот остановлен")
        except Exception as e:
            logger.error(f"Ошибка при запуске бота: {e}")
            raise
    else:
        logger.info("RENDER_EXTERNAL_URL не найден, запускаю в режиме polling")
        
        # Запускаем в режиме polling
        try:
            asyncio.run(run_polling())
        except KeyboardInterrupt:
            logger.info("Бот остановлен")
        except Exception as e:
            logger.error(f"Ошибка при запуске бота: {e}")
            raise

if __name__ == "__main__":
    main()