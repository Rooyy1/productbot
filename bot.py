import os
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional
from enum import Enum
from dataclasses import dataclass, asdict
from dotenv import load_dotenv

# Импорты aiogram
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
import asyncio

# Загрузка переменных окружения
load_dotenv()

# Получаем токен бота
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN не найден в переменных окружения!")

# Получаем URL Render из переменных окружения (для webhook)
RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL")
if RENDER_EXTERNAL_URL:
    WEBHOOK_URL = f"{RENDER_EXTERNAL_URL}/webhook"
else:
    # Fallback для локальной разработки
    WEBHOOK_URL = None

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

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

# Хранилище данных пользователей (в памяти, для демонстрации)
# В реальном приложении лучше использовать базу данных
user_progress_db: Dict[int, UserProgress] = {}

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# ========== СОСТОЯНИЯ ==========

class CourseStates(StatesGroup):
    awaiting_assignment_submission = State()

# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========

def _create_progress_bar(percentage: float) -> str:
    """Создать текстовый прогресс-бар"""
    bars = 10
    filled = int(percentage / 100 * bars)
    return "█" * filled + "░" * (bars - filled)

# ========== ОБРАБОТЧИКИ КОМАНД ==========

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    """Обработчик команды /start"""
    user = message.from_user
    
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
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🚀 Начать курс", callback_data="start_course")],
            [InlineKeyboardButton(text="📊 Мой прогресс", callback_data="profile")],
            [InlineKeyboardButton(text="ℹ️ О курсе", callback_data="about_course")]
        ]
    )
    
    await message.answer(welcome_message, reply_markup=keyboard, parse_mode='Markdown')

@dp.message(Command("menu"))
async def cmd_menu(message: types.Message):
    """Главное меню"""
    await show_main_menu(message)

@dp.message(Command("progress"))
async def cmd_progress(message: types.Message):
    """Показать прогресс"""
    await show_progress(message)

# ========== ОБРАБОТЧИКИ КОЛБЭКОВ ==========

@dp.callback_query(F.data == "main_menu")
async def main_menu_callback(callback: CallbackQuery):
    """Главное меню"""
    await show_main_menu(callback.message, callback.from_user.id, edit=True)
    await callback.answer()

@dp.callback_query(F.data == "start_course")
async def start_course_callback(callback: CallbackQuery):
    """Начать курс"""
    user = callback.from_user
    progress = user_progress_db.get(user.id, UserProgress(user_id=user.id))
    progress.status = UserStatus.IN_PROGRESS
    user_progress_db[user.id] = progress
    await show_lesson(callback.message, user.id, 1, edit=True)
    await callback.answer()

@dp.callback_query(F.data == "profile")
async def profile_callback(callback: CallbackQuery):
    """Показать прогресс"""
    await show_progress(callback.message, callback.from_user.id, edit=True)
    await callback.answer()

@dp.callback_query(F.data == "about_course")
async def about_course_callback(callback: CallbackQuery):
    """О курсе"""
    await callback.message.edit_text(
        COURSE_DESCRIPTION,
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🚀 Начать обучение", callback_data="start_course")],
                [InlineKeyboardButton(text="🏠 В главное меню", callback_data="main_menu")]
            ]
        ),
        parse_mode='Markdown'
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("lesson_"))
async def lesson_callback(callback: CallbackQuery):
    """Показать урок"""
    lesson_id = int(callback.data.split("_")[1])
    await show_lesson(callback.message, callback.from_user.id, lesson_id, edit=True)
    await callback.answer()

@dp.callback_query(F.data.startswith("submit_"))
async def submit_assignment_callback(callback: CallbackQuery, state: FSMContext):
    """Сдать задание"""
    lesson_id = int(callback.data.split("_")[1])
    await state.set_state(CourseStates.awaiting_assignment_submission)
    await state.update_data(lesson_id=lesson_id)
    
    lesson = LESSONS[lesson_id - 1]
    
    await callback.message.edit_text(
        f"✍️ *Отправьте ваш ответ на задание:*\n\n{lesson.assignment_question}\n\n"
        f"💡 *Подсказка:* {lesson.assignment_hint}\n\n"
        "Просто напишите сообщение с вашим ответом в чат.",
        parse_mode='Markdown'
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("check_"))
async def check_assignment_callback(callback: CallbackQuery):
    """Проверить задание"""
    lesson_id = int(callback.data.split("_")[1])
    await show_submitted_assignment(callback.message, callback.from_user.id, lesson_id, edit=True)
    await callback.answer()

@dp.callback_query(F.data.startswith("complete_lesson_"))
async def complete_lesson_callback(callback: CallbackQuery):
    """Завершить урок"""
    lesson_id = int(callback.data.split("_")[2])
    await complete_lesson(callback.message, callback.from_user.id, lesson_id, edit=True)
    await callback.answer()

@dp.callback_query(F.data.startswith("assignment_"))
async def assignment_callback(callback: CallbackQuery):
    """Показать задание"""
    lesson_id = int(callback.data.split("_")[1])
    await show_assignment(callback.message, callback.from_user.id, lesson_id, edit=True)
    await callback.answer()

@dp.callback_query(F.data == "about_author")
async def about_author_callback(callback: CallbackQuery):
    """Об авторе"""
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
    
    await callback.message.edit_text(
        author_info,
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="📚 Начать курс", callback_data="start_course")],
                [InlineKeyboardButton(text="🏠 В главное меню", callback_data="main_menu")]
            ]
        ),
        parse_mode='Markdown'
    )
    await callback.answer()

@dp.callback_query(F.data == "feedback")
async def feedback_callback(callback: CallbackQuery):
    """Отзыв о курсе"""
    await callback.message.edit_text(
        "📝 *Оставьте отзыв о курсе*\n\n"
        "Ваше мнение очень важно для нас! Напишите, что понравилось, "
        "а что можно улучшить. Это поможет сделать курс еще лучше!\n\n"
        "Просто отправьте ваше сообщение с отзывом в чат.",
        parse_mode='Markdown'
    )
    await callback.answer()

# ========== ОБРАБОТЧИКИ СООБЩЕНИЙ ==========

@dp.message(CourseStates.awaiting_assignment_submission)
async def handle_assignment_submission(message: types.Message, state: FSMContext):
    """Обработка сдачи домашнего задания"""
    user = message.from_user
    user_data = await state.get_data()
    lesson_id = user_data.get('lesson_id')
    
    if not lesson_id:
        await message.answer("Ошибка. Пожалуйста, попробуйте еще раз.")
        await state.clear()
        return
    
    progress = user_progress_db.get(user.id, UserProgress(user_id=user.id))
    
    # Сохраняем ответ
    progress.submitted_assignments[lesson_id] = message.text
    progress.checked_assignments[lesson_id] = False
    user_progress_db[user.id] = progress
    
    # Очищаем состояние
    await state.clear()
    
    # Отправляем подтверждение
    confirmation_message = f"""
✅ *Ваше задание к уроку {lesson_id} принято!*

Александр или куратор проверят его в ближайшее время.

💡 *Совет от Александра:*
"Лучший способ научиться - это практика. Даже если ваш ответ не идеален, вы уже сделали важный шаг."

📊 Проверить статус всех заданий можно в разделе "Мой прогресс".
    """
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📚 Следующий урок", callback_data=f"lesson_{lesson_id + 1}")],
            [InlineKeyboardButton(text="📝 Посмотреть задание", callback_data=f"check_{lesson_id}")],
            [InlineKeyboardButton(text="📊 Мой прогресс", callback_data="profile")]
        ]
    )
    
    await message.answer(confirmation_message, reply_markup=keyboard, parse_mode='Markdown')

@dp.message()
async def handle_text(message: types.Message):
    """Обработка обычных текстовых сообщений"""
    if message.text and not message.text.startswith('/'):
        await message.answer("Выберите раздел из меню:", reply_markup=get_main_menu_keyboard())

# ========== ОСНОВНЫЕ ФУНКЦИИ ==========

def get_main_menu_keyboard():
    """Клавиатура главного меню"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📚 Продолжить обучение", callback_data="lesson_1")],
            [InlineKeyboardButton(text="📊 Мой прогресс", callback_data="profile")],
            [InlineKeyboardButton(text="🏆 Домашние задания", callback_data="assignment_1")],
            [InlineKeyboardButton(text="👨‍🏫 Об авторе", callback_data="about_author")]
        ]
    )

async def show_main_menu(message: types.Message, user_id: int = None, edit: bool = False):
    """Показать главное меню"""
    if not user_id and message:
        user_id = message.from_user.id
    
    message_text = "🏠 *Главное меню курса*\nВыберите действие:"
    keyboard = get_main_menu_keyboard()
    
    if edit:
        await message.edit_text(message_text, reply_markup=keyboard, parse_mode='Markdown')
    else:
        await message.answer(message_text, reply_markup=keyboard, parse_mode='Markdown')

async def show_progress(message: types.Message, user_id: int = None, edit: bool = False):
    """Показать прогресс пользователя"""
    if not user_id and message:
        user_id = message.from_user.id
    
    progress = user_progress_db.get(user_id, UserProgress(user_id=user_id))
    
    completed = len(progress.completed_lessons)
    total = len(LESSONS)
    percentage = (completed / total * 100) if total > 0 else 0
    
    submitted = len(progress.submitted_assignments)
    checked = sum(1 for checked in progress.checked_assignments.values() if checked)
    
    progress_text = f"""
📊 *Ваш прогресс*

🎯 **Прогресс по курсу:**
{_create_progress_bar(percentage)} {percentage:.1f}%
✅ Пройдено уроков: {completed}/{total}

📝 **Домашние задания:**
📤 Сдано: {submitted}/{total}
✅ Проверено: {checked}/{total}

🏆 **Текущий статус:** {progress.status.value.replace('_', ' ').title()}
📖 **Текущий урок:** {progress.current_lesson}/{total}

💡 *Продолжайте в том же духе! Каждый урок приближает вас к результату.*
    """
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📚 Продолжить обучение", callback_data=f"lesson_{progress.current_lesson}")],
            [InlineKeyboardButton(text="📝 Мои задания", callback_data=f"assignment_{progress.current_lesson}")],
            [InlineKeyboardButton(text="🏠 В главное меню", callback_data="main_menu")]
        ]
    )
    
    if edit:
        await message.edit_text(progress_text, reply_markup=keyboard, parse_mode='Markdown')
    else:
        await message.answer(progress_text, reply_markup=keyboard, parse_mode='Markdown')

async def show_lesson(message: types.Message, user_id: int, lesson_id: int, edit: bool = False):
    """Показать урок"""
    progress = user_progress_db.get(user_id, UserProgress(user_id=user_id))
    
    if lesson_id < 1 or lesson_id > len(LESSONS):
        # Отправляем сообщение об ошибке, если это новый запрос
        if not edit:
            await message.answer("Урок не найден")
        return
    
    lesson = LESSONS[lesson_id - 1]
    progress.current_lesson = lesson_id
    user_progress_db[user_id] = progress
    
    # Формируем сообщение урока
    lesson_message = f"""
📖 *Урок {lesson_id}: {lesson.title}*

{lesson.text_content}

🎬 *Видео-материал:* {lesson.video_url if lesson.video_url else "Скоро будет добавлено"}
    """
    
    # Создаем клавиатуру
    keyboard_buttons = []
    
    if lesson.assignment_question:
        keyboard_buttons.append([InlineKeyboardButton(
            text="📝 Домашнее задание", 
            callback_data=f"submit_{lesson_id}"
        )])
    
    # Кнопки навигации
    nav_buttons = []
    if lesson_id > 1:
        nav_buttons.append(InlineKeyboardButton(
            text="◀️ Предыдущий", 
            callback_data=f"lesson_{lesson_id - 1}"
        ))
    
    if lesson_id < len(LESSONS):
        nav_buttons.append(InlineKeyboardButton(
            text="Следующий ▶️", 
            callback_data=f"lesson_{lesson_id + 1}"
        ))
    
    if nav_buttons:
        keyboard_buttons.append(nav_buttons)
    
    keyboard_buttons.extend([
        [InlineKeyboardButton(text="✅ Отметить как пройденный", callback_data=f"complete_lesson_{lesson_id}")],
        [InlineKeyboardButton(text="📊 Мой прогресс", callback_data="profile")],
        [InlineKeyboardButton(text="🏠 В главное меню", callback_data="main_menu")]
    ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    # Отправляем или редактируем сообщение
    if edit:
        await message.edit_text(lesson_message, reply_markup=keyboard, parse_mode='Markdown')
    else:
        await message.answer(lesson_message, reply_markup=keyboard, parse_mode='Markdown')

async def show_assignment(message: types.Message, user_id: int, lesson_id: int, edit: bool = False):
    """Показать домашнее задание"""
    progress = user_progress_db.get(user_id, UserProgress(user_id=user_id))
    
    if lesson_id < 1 or lesson_id > len(LESSONS):
        # Если это callback, отвечаем всплывающим сообщением
        if edit:
            # Для edit режима отправляем новое сообщение
            await message.answer("Урок не найден")
        return
    
    lesson = LESSONS[lesson_id - 1]
    
    if not lesson.assignment_question:
        if edit:
            await message.edit_text("Для этого урока нет задания")
        else:
            await message.answer("Для этого урока нет задания")
        return
    
    assignment_status = "❌ Не сдано"
    if lesson_id in progress.submitted_assignments:
        assignment_status = "📤 Сдано (ожидает проверки)" if not progress.checked_assignments.get(lesson_id) else "✅ Проверено"
    
    assignment_message = f"""
📝 *Домашнее задание к уроку {lesson_id}*

**Тема:** {lesson.title}

**Задание:**
{lesson.assignment_question}

💡 *Подсказка от Александра:*
{lesson.assignment_hint}

**Статус:** {assignment_status}
    """
    
    keyboard_buttons = []
    
    if lesson_id not in progress.submitted_assignments:
        keyboard_buttons.append([InlineKeyboardButton(
            text="📤 Сдать задание", 
            callback_data=f"submit_{lesson_id}"
        )])
    
    if lesson_id in progress.submitted_assignments:
        keyboard_buttons.append([InlineKeyboardButton(
            text="👀 Посмотреть мой ответ", 
            callback_data=f"check_{lesson_id}"
        )])
    
    keyboard_buttons.extend([
        [InlineKeyboardButton(text="📚 Вернуться к уроку", callback_data=f"lesson_{lesson_id}")],
        [InlineKeyboardButton(text="📊 Все задания", callback_data="assignment_1")],
        [InlineKeyboardButton(text="🏠 В главное меню", callback_data="main_menu")]
    ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    if edit:
        await message.edit_text(assignment_message, reply_markup=keyboard, parse_mode='Markdown')
    else:
        await message.answer(assignment_message, reply_markup=keyboard, parse_mode='Markdown')

async def show_submitted_assignment(message: types.Message, user_id: int, lesson_id: int, edit: bool = False):
    """Показать сданное задание"""
    progress = user_progress_db.get(user_id, UserProgress(user_id=user_id))
    
    answer = progress.submitted_assignments.get(lesson_id, "")
    
    if not answer:
        if edit:
            await message.edit_text("Задание еще не сдано")
        else:
            await message.answer("Задание еще не сдано")
        return
    
    is_checked = progress.checked_assignments.get(lesson_id, False)
    status = "✅ Проверено" if is_checked else "📤 Ожидает проверки"
    
    message_text = f"""
📝 *Ваш ответ к уроку {lesson_id}*

**Статус:** {status}

**Ваш ответ:**
{answer[:1500]}{'...' if len(answer) > 1500 else ''}
    """
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📚 Вернуться к уроку", callback_data=f"lesson_{lesson_id}")],
            [InlineKeyboardButton(text="📝 Все задания", callback_data="assignment_1")],
            [InlineKeyboardButton(text="🏠 В главное меню", callback_data="main_menu")]
        ]
    )
    
    if edit:
        await message.edit_text(message_text, reply_markup=keyboard, parse_mode='Markdown')
    else:
        await message.answer(message_text, reply_markup=keyboard, parse_mode='Markdown')

async def complete_lesson(message: types.Message, user_id: int, lesson_id: int, edit: bool = False):
    """Отметить урок как пройденный"""
    progress = user_progress_db.get(user_id, UserProgress(user_id=user_id))
    
    if lesson_id not in progress.completed_lessons:
        progress.completed_lessons.append(lesson_id)
        user_progress_db[user_id] = progress
    
    # Проверяем, завершен ли весь курс
    if len(progress.completed_lessons) == len(LESSONS):
        progress.status = UserStatus.COMPLETED
        
        completion_message = f"""
🏆 *Поздравляем!*

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
        
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="📊 Итоговый прогресс", callback_data="profile")],
                [InlineKeyboardButton(text="📝 Все задания", callback_data="assignment_1")],
                [InlineKeyboardButton(text="👨‍🏫 Оставить отзыв", callback_data="feedback")]
            ]
        )
        
        if edit:
            await message.edit_text(completion_message, reply_markup=keyboard, parse_mode='Markdown')
        else:
            await message.answer(completion_message, reply_markup=keyboard, parse_mode='Markdown')
    else:
        # Отправляем всплывающее уведомление
        if hasattr(message, 'answer'):
            await message.answer(f"Урок {lesson_id} отмечен как пройденный! ✅")
        
        # Показываем следующий урок
        next_lesson = lesson_id + 1 if lesson_id < len(LESSONS) else lesson_id
        if edit:
            await show_lesson(message, user_id, next_lesson, edit=True)
        else:
            await show_lesson(message, user_id, next_lesson)

# ========== WEBHOOK НАСТРОЙКИ ==========

async def on_startup(bot: Bot):
    """Установка webhook при запуске"""
    if WEBHOOK_URL:
        webhook_info = await bot.get_webhook_info()
        if webhook_info.url != WEBHOOK_URL:
            await bot.set_webhook(
                url=WEBHOOK_URL,
                drop_pending_updates=True
            )
            logger.info(f"Webhook установлен на {WEBHOOK_URL}")
        else:
            logger.info("Webhook уже установлен")
    else:
        logger.warning("WEBHOOK_URL не задан. Работаю в polling режиме.")

async def on_shutdown(bot: Bot):
    """Удаление webhook при остановке"""
    if WEBHOOK_URL:
        await bot.delete_webhook()
        logger.info("Webhook удален")

async def health_check(request):
    """Health check endpoint для Render"""
    return web.Response(text="OK", status=200)

async def handle_main(request):
    """Корневой endpoint"""
    return web.Response(text="Telegram Bot is running! Use /start in Telegram.", status=200)

# ========== ЗАПУСК ПРИЛОЖЕНИЯ ==========

async def main_webhook():
    """Запуск в режиме Webhook"""
    logger.info("Запуск бота в режиме Webhook...")
    
    # Регистрируем обработчики startup/shutdown
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    
    # Создаем aiohttp приложение
    app = web.Application()
    
    # Регистрируем health check и корневой endpoint
    app.router.add_get("/health", health_check)
    app.router.add_get("/", handle_main)
    
    # Создаем обработчик webhook
    webhook_handler = SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
    )
    
    # Регистрируем webhook endpoint
    webhook_handler.register(app, path="/webhook")
    
    # Настраиваем приложение aiogram
    setup_application(app, dp, bot=bot)
    
    # Получаем порт из переменной окружения
    port = int(os.environ.get("PORT", 10000))
    host = "0.0.0.0"
    
    logger.info(f"Запуск сервера на {host}:{port}")
    if WEBHOOK_URL:
        logger.info(f"Webhook URL: {WEBHOOK_URL}")
    
    print("=" * 50)
    print("Бот запущен в режиме Webhook!")
    print(f"Сервер запущен на {host}:{port}")
    if WEBHOOK_URL:
        print(f"Webhook URL: {WEBHOOK_URL}")
    print("=" * 50)
    
    # Запускаем сервер
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()
    
    # Бесконечный цикл
    await asyncio.Event().wait()

async def main_polling():
    """Запуск в режиме Polling (для локальной разработки)"""
    logger.info("Запуск бота в режиме Polling...")
    
    # Удаляем webhook перед запуском polling
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("Webhook удален, запускаем polling...")
    except Exception as e:
        logger.warning(f"Ошибка при удалении webhook: {e}")
    
    await dp.start_polling(bot)
    
if __name__ == "__main__":
    try:
        # Если задан WEBHOOK_URL - запускаем в режиме webhook
        if WEBHOOK_URL:
            asyncio.run(main_webhook())
        else:
            # Иначе запускаем в режиме polling (для локальной разработки)
            asyncio.run(main_polling())
    except KeyboardInterrupt:
        logger.info("Бот остановлен")
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")