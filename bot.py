import asyncio
import os
import datetime
import uuid  # <--- Добавлено для генерации ID платежей
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram_calendar.simple_calendar import SimpleCalendar, SimpleCalendarCallback
from aiogram.fsm.storage.memory import MemoryStorage
from .db import SessionLocal
# <--- Добавлены новые модели в импорт
from .models import (
    Teacher, Student, Group, GroupStudent, Lesson,
    Homework, HomeworkAssignment, HomeworkSubmission,
    Parent, ParentStudent, SaaSPayment, StudentPayment
)

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set in environment")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())


# ======= Клавиатуры =======

MAIN_KB = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="➕ Добавить ученика"), KeyboardButton(text="👥 Создать группу")],
        [KeyboardButton(text="📅 Назначить урок"), KeyboardButton(text="📝 Создать ДЗ")],
        [KeyboardButton(text="Финансы учеников"), KeyboardButton(text="💳 Подписка")], # Изменено
        [KeyboardButton(text="📚 Мои назначения"), KeyboardButton(text="🏠 Главное меню")]
    ],
    resize_keyboard=True
)

BACK_KB = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="⬅️ Назад"), KeyboardButton(text="🏠 Главное меню")]],
    resize_keyboard=True
)

# <--- Новая клавиатура для симуляции оплаты
PAYMENT_KB = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="💳 Купить PRO (Тест)"), KeyboardButton(text="⬅️ Назад")]
    ],
    resize_keyboard=True
)


# ======= Навигация =======
@dp.message(F.text == "⬅️ Назад")
async def handle_back(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Вернулись назад.", reply_markup=MAIN_KB)


@dp.message(F.text == "🏠 Главное меню")
async def handle_main_menu(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Главное меню", reply_markup=MAIN_KB)


# ===== START =====
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "Привет! 👨‍🏫 Это бот Класс Рум!\n\n"
        "Для учителей: /register_teacher\n"
        "Для родителей: /register_parent\n"
        "Для учеников: просто ожидайте добавления учителем.\n\n"
        "Выбирай действие ниже 👇",
        reply_markup=MAIN_KB
    )


# ===== Регистрация Учителя =====
@dp.message(Command("register_teacher"))
async def register_teacher(message: types.Message):
    tg_id = str(message.from_user.id)
    name = message.from_user.full_name

    with SessionLocal() as db:
        t = db.query(Teacher).filter_by(telegram_id=tg_id).first()
        if t:
            await message.answer("Вы уже зарегистрированы как преподаватель.")
            return

        teacher = Teacher(telegram_id=tg_id, name=name)
        db.add(teacher)
        db.commit()

    await message.answer("✅ Вы зарегистрированы как преподаватель.", reply_markup=MAIN_KB)


# ===== Регистрация Родителя (НОВОЕ) =====
@dp.message(Command("register_parent"))
async def register_parent(message: types.Message):
    tg_id = str(message.from_user.id)
    name = message.from_user.full_name

    with SessionLocal() as db:
        # Проверяем, не учитель ли это (опционально)
        if db.query(Teacher).filter_by(telegram_id=tg_id).first():
            await message.answer("Вы уже зарегистрированы как учитель.")
            return

        parent = db.query(Parent).filter_by(telegram_id=tg_id).first()
        if parent:
            await message.answer("Вы уже зарегистрированы как Родитель.")
            return

        parent = Parent(telegram_id=tg_id, name=name)
        db.add(parent)
        db.commit()

    await message.answer(
        "👨‍👩‍👧 Вы зарегистрированы как Родитель.\n"
        "Чтобы привязать ребенка, узнайте его ID у учителя и введите команду:\n"
        "/link_child <ID_ученика>",
        reply_markup=MAIN_KB
    )


# ===== Привязка ребенка родителем (НОВОЕ) =====
@dp.message(Command("link_child"))
async def link_child(message: types.Message):
    # Ожидаем формат: /link_child 123
    args = message.text.split()
    if len(args) != 2 or not args[1].isdigit():
        await message.answer("❌ Неверный формат.\nИспользуйте: /link_child <ID_ученика>")
        return

    student_id = int(args[1])
    parent_tg = str(message.from_user.id)

    with SessionLocal() as db:
        parent = db.query(Parent).filter_by(telegram_id=parent_tg).first()
        if not parent:
            await message.answer("Сначала зарегистрируйтесь: /register_parent")
            return

        student = db.query(Student).filter_by(id=student_id).first()
        if not student:
            await message.answer("❌ Ученик с таким ID не найден.")
            return

        # Проверка дублей
        link = db.query(ParentStudent).filter_by(parent_id=parent.id, student_id=student.id).first()
        if link:
            await message.answer("⚠️ Этот ученик уже привязан к вам.")
            return

        new_link = ParentStudent(parent_id=parent.id, student_id=student.id)
        db.add(new_link)
        db.commit()

        await message.answer(f"✅ Ученик {student.name} успешно привязан! Теперь вы видите его прогресс.")


# ===== SaaS: Меню подписки (НОВОЕ) =====
@dp.message(F.text == "💳 Подписка")
async def subscription_menu(message: types.Message):
    tg_id = str(message.from_user.id)
    with SessionLocal() as db:
        teacher = db.query(Teacher).filter_by(telegram_id=tg_id).first()
        if not teacher:
            await message.answer("Эта функция только для учителей.")
            return
        
        plan = teacher.subscription_plan
        end_date = teacher.subscription_end_date
        
        info = f"💎 Ваш тариф: <b>{plan}</b>\n"
        if end_date:
            info += f"⏳ Действует до: {end_date.strftime('%d.%m.%Y')}\n"
        else:
            info += "⏳ Срок действия: Бессрочно (FREE)\n"

        if plan == "FREE":
            info += "\n🚀 Перейдите на PRO, чтобы получить больше возможностей!"

        await message.answer(info, parse_mode="HTML", reply_markup=PAYMENT_KB)


# ===== SaaS: Симуляция оплаты (НОВОЕ) =====
@dp.message(F.text == "💳 Купить PRO (Тест)")
async def simulate_payment(message: types.Message):
    tg_id = str(message.from_user.id)
    amount = 1000 # Цена PRO
    
    with SessionLocal() as db:
        teacher = db.query(Teacher).filter_by(telegram_id=tg_id).first()
        if not teacher:
            return

        # 1. Создаем запись о платеже
        payment_id = str(uuid.uuid4())
        payment = SaaSPayment(
            teacher_id=teacher.id,
            amount=amount,
            provider_payment_id=payment_id,
            status="pending"
        )
        db.add(payment)
        db.commit()
        db.refresh(payment)

        # 2. СИМУЛЯЦИЯ: Сразу меняем статус на success
        payment.status = "succeeded"
        
        # 3. Обновляем подписку учителя
        teacher.subscription_plan = "PRO"
        
        # Продлеваем на 30 дней
        now = datetime.datetime.utcnow()
        if teacher.subscription_end_date and teacher.subscription_end_date > now:
            teacher.subscription_end_date += datetime.timedelta(days=30)
        else:
            teacher.subscription_end_date = now + datetime.timedelta(days=30)
            
        db.commit()
        end_date_str = teacher.subscription_end_date.strftime('%d.%m.%Y')

    await message.answer(
        f"✅ Оплата прошла успешно (Симуляция)!\n"
        f"🎉 Тариф PRO активирован до {end_date_str}",
        reply_markup=MAIN_KB
    )


# ===== Добавление ученика =====
class AddStudent(StatesGroup):
    waiting_for_name = State()


@dp.message(F.text == "➕ Добавить ученика")
async def btn_add_student(message: types.Message, state: FSMContext):
    await message.answer("Введите ФИО ученика:", reply_markup=BACK_KB)
    await state.set_state(AddStudent.waiting_for_name)


@dp.message(AddStudent.waiting_for_name)
async def process_student_name(message: types.Message, state: FSMContext):
    name = message.text.strip()
    teacher_tg = str(message.from_user.id)

    with SessionLocal() as db:
        teacher = db.query(Teacher).filter_by(telegram_id=teacher_tg).first()
        if not teacher:
            await message.answer("Сначала зарегистрируйтесь: /register_teacher")
            await state.clear()
            return

        student = Student(name=name, teacher_id=teacher.id)
        db.add(student)
        db.commit()
        # Важно получить ID для родителя
        db.refresh(student) 

    await message.answer(f"👨‍🎓 Ученик {name} добавлен 🎉\n🆔 ID ученика: {student.id} (передайте его родителю для привязки)", reply_markup=MAIN_KB)
    await state.clear()


# ===== Группа =====
class CreateGroup(StatesGroup):
    waiting_for_title = State()


@dp.message(F.text == "👥 Создать группу")
async def btn_create_group(message: types.Message, state: FSMContext):
    await message.answer("Введите название группы:", reply_markup=BACK_KB)
    await state.set_state(CreateGroup.waiting_for_title)


@dp.message(CreateGroup.waiting_for_title)
async def process_group_title(message: types.Message, state: FSMContext):
    title = message.text.strip()
    teacher_tg = str(message.from_user.id)

    with SessionLocal() as db:
        teacher = db.query(Teacher).filter_by(telegram_id=teacher_tg).first()
        if not teacher:
            await message.answer("Сначала зарегистрируйтесь: /register_teacher")
            await state.clear()
            return

        group = Group(title=title, teacher_id=teacher.id)
        db.add(group)
        db.commit()

    await message.answer(f"👥 Группа '{title}' создана ✅", reply_markup=MAIN_KB)
    await state.clear()


# ===== Урок =====
class ScheduleLesson(StatesGroup):
    waiting_for_date = State()
    waiting_for_time = State()
    waiting_for_topic = State()

@dp.message(F.text == "📅 Назначить урок")
async def btn_schedule(message: types.Message, state: FSMContext):
    await state.set_state(ScheduleLesson.waiting_for_date)
    await message.answer(
        "📅 Выберите дату урока:",
        reply_markup=await SimpleCalendar().start_calendar()
    )

@dp.callback_query(SimpleCalendarCallback.filter())
async def calendar_handler(callback: types.CallbackQuery, callback_data: SimpleCalendarCallback, state: FSMContext):
    selected, date = await SimpleCalendar().process_selection(callback, callback_data)

    if selected:
        await state.update_data(date=date.strftime("%Y-%m-%d"))
        await callback.message.answer(f"Дата выбрана: {date.strftime('%Y-%m-%d')}")
        await callback.message.answer("Введите время (HH:MM):")
        await state.set_state(ScheduleLesson.waiting_for_time)

@dp.message(ScheduleLesson.waiting_for_time)
async def lesson_time(message: types.Message, state: FSMContext):
    await state.update_data(time=message.text.strip())
    await message.answer("Введите тему урока:")
    await state.set_state(ScheduleLesson.waiting_for_topic)


@dp.message(ScheduleLesson.waiting_for_topic)
async def lesson_topic(message: types.Message, state: FSMContext):
    data = await state.get_data()

    try:
        dt = datetime.datetime.strptime(
            f"{data['date']} {data['time']}",
            "%Y-%m-%d %H:%M"
        )
    except:
        await message.answer("❌ Неверный формат.", reply_markup=MAIN_KB)
        await state.clear()
        return

    teacher_tg = str(message.from_user.id)

    with SessionLocal() as db:
        teacher = db.query(Teacher).filter_by(telegram_id=teacher_tg).first()
        if not teacher:
            await message.answer("Сначала зарегистрируйтесь.", reply_markup=MAIN_KB)
            await state.clear()
            return

        lesson = Lesson(
            teacher_id=teacher.id,
            topic=message.text.strip(),
            start_time=dt
        )
        db.add(lesson)
        db.commit()

    await message.answer("📅 Урок назначен!", reply_markup=MAIN_KB)
    await state.clear()


# ===== ДЗ: создание =======
class CreateHomework(StatesGroup):
    waiting_for_title = State()
    waiting_for_content = State()
    waiting_for_max_score = State()
    waiting_for_saved_in_library = State()


@dp.message(F.text == "📝 Создать ДЗ")
@dp.message(Command("create_homework"))
async def create_hw(message: types.Message, state: FSMContext):
    await message.answer("Введите заголовок:", reply_markup=BACK_KB)
    await state.set_state(CreateHomework.waiting_for_title)


@dp.message(CreateHomework.waiting_for_title)
async def hw_title(message: types.Message, state: FSMContext):
    await state.update_data(title=message.text.strip())
    await message.answer("Введите описание или 'skip':", reply_markup=BACK_KB)
    await state.set_state(CreateHomework.waiting_for_content)


@dp.message(CreateHomework.waiting_for_content)
async def hw_content(message: types.Message, state: FSMContext):
    text = message.text.strip()
    await state.update_data(content=None if text.lower() == "skip" else text)
    await message.answer("Введите максимальный балл или 'skip':", reply_markup=BACK_KB)
    await state.set_state(CreateHomework.waiting_for_max_score)


@dp.message(CreateHomework.waiting_for_max_score)
async def hw_score(message: types.Message, state: FSMContext):
    text = message.text.strip()
    max_score = None

    if text.lower() != "skip":
        try:
            max_score = int(text)
        except:
            await message.answer("Введите число.", reply_markup=BACK_KB)
            return

    await state.update_data(max_score=max_score)
    await message.answer("Сохранить в библиотеке? yes/no", reply_markup=BACK_KB)
    await state.set_state(CreateHomework.waiting_for_saved_in_library)


@dp.message(CreateHomework.waiting_for_saved_in_library)
async def hw_save(message: types.Message, state: FSMContext):
    saved = message.text.strip().lower() in ("yes", "y", "да")
    data = await state.get_data()
    teacher_tg = str(message.from_user.id)

    with SessionLocal() as db:
        teacher = db.query(Teacher).filter_by(telegram_id=teacher_tg).first()
        if not teacher:
            await message.answer("Сначала /register_teacher", reply_markup=MAIN_KB)
            await state.clear()
            return

        hw = Homework(
            teacher_id=teacher.id,
            title=data["title"],
            content=data.get("content"),
            max_score=data.get("max_score"),
            saved_in_library=saved
        )
        db.add(hw)
        db.commit()
        db.refresh(hw)

    await message.answer(f"✅ Домашка создана. ID: {hw.id}", reply_markup=MAIN_KB)
    await state.clear()


# ======= Мои назначения =======
@dp.message(F.text == "📚 Мои назначения")
@dp.message(Command("my_assignments"))
async def my_assignments(message: types.Message):
    teacher_tg = str(message.from_user.id)

    with SessionLocal() as db:
        teacher = db.query(Teacher).filter_by(telegram_id=teacher_tg).first()
        if not teacher:
            await message.answer("Сначала зарегистрируйтесь.", reply_markup=MAIN_KB)
            return

        assigns = (
            db.query(HomeworkAssignment)
            .join(Homework)
            .filter(Homework.teacher_id == teacher.id)
            .all()
        )

        if not assigns:
            await message.answer("Назначений нет.", reply_markup=MAIN_KB)
            return

        text = ""
        for a in assigns:
            text += f"ID:{a.id} HW:{a.homework.title} deadline:{a.deadline}\n"

        await message.answer(text, reply_markup=MAIN_KB)


# ======= Загрузка файлов =======
@dp.message(F.document)
async def submit_file(message: types.Message):
    caption = (message.caption or "").strip()

    if not caption or not caption.split()[0].isdigit():
        await message.answer("Укажи AssignID в caption, пример: 5", reply_markup=MAIN_KB)
        return

    assign_id = int(caption.split()[0])
    student_tg = str(message.from_user.id)

    with SessionLocal() as db:
        student = db.query(Student).filter_by(telegram_id=student_tg).first()
        if not student:
            await message.answer("Сначала зарегистрируйтесь как ученик.", reply_markup=MAIN_KB)
            return

        assignment = db.query(HomeworkAssignment).filter_by(id=assign_id).first()
        if not assignment:
            await message.answer("Назначение не найдено.", reply_markup=MAIN_KB)
            return

        if assignment.deadline and datetime.datetime.utcnow() > assignment.deadline:
            await message.answer("Дедлайн прошёл.", reply_markup=MAIN_KB)
            return

        file = await message.document.get_file()
        os.makedirs("data/submissions", exist_ok=True)

        local_name = f"data/submissions/{assign_id}_{student.id}_{message.document.file_name}"
        await file.download(destination=local_name)

        submission = HomeworkSubmission(
            assignment_id=assign_id,
            student_id=student.id,
            file_path=local_name,
            status="submitted"
        )

        db.add(submission)
        db.commit()
        db.refresh(submission)

        hw = db.query(Homework).filter_by(id=assignment.homework_id).first()
        teacher = db.query(Teacher).filter_by(id=hw.teacher_id).first()

    await message.answer(f"Файл принят. Submission ID: {submission.id}", reply_markup=MAIN_KB)

    if teacher and teacher.telegram_id:
        await bot.send_message(
            int(teacher.telegram_id),
            f"📬 Новая работа. HW: {hw.title}"
        )


# ======= Оценка =======
@dp.message(Command("grade_submission"))
async def grade(message: types.Message):
    parts = message.text.strip().split(maxsplit=3)

    if len(parts) < 3:
        await message.answer(
            "Использование:\n/grade_submission <submission_id> <score> <comment>",
            reply_markup=MAIN_KB
        )
        return

    sub_id = int(parts[1])
    score = int(parts[2])
    comment = parts[3] if len(parts) > 3 else None
    teacher_tg = str(message.from_user.id)

    with SessionLocal() as db:
        teacher = db.query(Teacher).filter_by(telegram_id=teacher_tg).first()
        if not teacher:
            await message.answer("Сначала зарегистрируйтесь.", reply_markup=MAIN_KB)
            return

        submission = db.query(HomeworkSubmission).filter_by(id=sub_id).first()
        if not submission:
            await message.answer("Submission не найден.", reply_markup=MAIN_KB)
            return

        assignment = db.query(HomeworkAssignment).filter_by(id=submission.assignment_id).first()
        hw = db.query(Homework).filter_by(id=assignment.homework_id).first()

        if hw.teacher_id != teacher.id:
            await message.answer("Это не ваша работа.", reply_markup=MAIN_KB)
            return

        submission.score_value = score
        submission.score_percent = int(score / hw.max_score * 100) if hw.max_score else None
        submission.teacher_comment = comment
        submission.status = "graded"
        db.commit()

    await message.answer("Оценка выставлена.", reply_markup=MAIN_KB)

# ======= Финансы учеников (НОВОЕ) =======
class StudentFinance(StatesGroup):
    waiting_for_student_id = State()
    waiting_for_amount = State()
    waiting_for_lessons = State()

@dp.message(F.text.func(lambda t: t and "Финансы учеников" in t))
async def student_finance_menu(message: types.Message):
    # Показываем список учеников с их балансом
    tg_id = str(message.from_user.id)
    with SessionLocal() as db:
        teacher = db.query(Teacher).filter_by(telegram_id=tg_id).first()
        if not teacher:
            await message.answer("Сначала зарегистрируйтесь.")
            return

        students = teacher.students
        if not students:
            await message.answer("У вас пока нет учеников.", reply_markup=MAIN_KB)
            return

        text = "<b>💰 Баланс учеников:</b>\n\n"
        for s in students:
            text += f"👤 <b>{s.name}</b> (ID: {s.id}) — Баланс: {s.balance} зан.\n"
        
        text += "\nЧтобы внести оплату, используйте команду:\n/add_payment <ID_ученика>"
        await message.answer(text, parse_mode="HTML", reply_markup=MAIN_KB)

@dp.message(Command("add_payment"))
async def add_payment_cmd(message: types.Message, state: FSMContext):
    args = message.text.split()
    if len(args) != 2 or not args[1].isdigit():
        await message.answer("Используйте: /add_payment <ID_ученика>")
        return
    
    student_id = int(args[1])
    await state.update_data(student_id=student_id)
    await message.answer("Введите сумму оплаты (руб):", reply_markup=BACK_KB)
    await state.set_state(StudentFinance.waiting_for_amount)

@dp.message(StudentFinance.waiting_for_amount)
async def process_payment_amount(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Введите число.")
        return
    
    await state.update_data(amount=int(message.text))
    await message.answer("Сколько занятий добавить на баланс?", reply_markup=BACK_KB)
    await state.set_state(StudentFinance.waiting_for_lessons)

@dp.message(StudentFinance.waiting_for_lessons)
async def process_payment_lessons(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Введите число.")
        return
    
    lessons_count = int(message.text)
    data = await state.get_data()
    
    teacher_tg = str(message.from_user.id)
    
    with SessionLocal() as db:
        teacher = db.query(Teacher).filter_by(telegram_id=teacher_tg).first()
        student = db.query(Student).filter_by(id=data['student_id'], teacher_id=teacher.id).first()
        
        if not student:
            await message.answer("Ученик не найден.", reply_markup=MAIN_KB)
            await state.clear()
            return
            
        # Запись платежа
        payment = StudentPayment(
            teacher_id=teacher.id,
            student_id=student.id,
            amount=data['amount'],
            lessons_added=lessons_count
        )
        # Обновление баланса
        student.balance += lessons_count
        
        db.add(payment)
        db.commit()
        
        await message.answer(
            f"✅ Оплата принята!\n"
            f"Ученик: {student.name}\n"
            f"Сумма: {data['amount']} руб.\n"
            f"Добавлено занятий: {lessons_count}\n"
            f"Текущий баланс: {student.balance}",
            reply_markup=MAIN_KB
        )
    await state.clear()

# ======= Кабинет Родителя (НОВОЕ) =======
PARENT_KB = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="👶 Мои дети"), KeyboardButton(text="📊 Отчет успеваемости")],
        [KeyboardButton(text="🏠 Главное меню")]
    ],
    resize_keyboard=True
)

@dp.message(F.text == "👶 Мои дети")
async def parent_children_list(message: types.Message):
    tg_id = str(message.from_user.id)
    with SessionLocal() as db:
        parent = db.query(Parent).filter_by(telegram_id=tg_id).first()
        if not parent:
            await message.answer("Вы не зарегистрированы как родитель. Нажмите /register_parent")
            return
            
        links = db.query(ParentStudent).filter_by(parent_id=parent.id).all()
        if not links:
            await message.answer("У вас нет привязанных детей. Используйте /link_child <ID>")
            return
            
        text = "<b>Ваши дети:</b>\n\n"
        for link in links:
            s = link.student
            teacher = db.query(Teacher).filter_by(id=s.teacher_id).first()
            text += f"👶 <b>{s.name}</b> (ID: {s.id})\n"
            text += f"   👨‍🏫 Преподаватель: {teacher.name if teacher else 'Неизвестно'}\n"
            text += f"   💰 Баланс занятий: {s.balance}\n\n"
            
        await message.answer(text, parse_mode="HTML", reply_markup=PARENT_KB)

@dp.message(F.text == "📊 Отчет успеваемости")
async def parent_report(message: types.Message):
    tg_id = str(message.from_user.id)
    with SessionLocal() as db:
        parent = db.query(Parent).filter_by(telegram_id=tg_id).first()
        if not parent:
            await message.answer("Сначала /register_parent")
            return

        links = db.query(ParentStudent).filter_by(parent_id=parent.id).all()
        if not links:
            await message.answer("Нет привязанных детей.")
            return

        report = "<b>📊 Отчет по успеваемости:</b>\n\n"
        
        for link in links:
            s = link.student
            # Берем последние 5 сданных работ
            submissions = (
                db.query(HomeworkSubmission)
                .filter_by(student_id=s.id, status='graded')
                .order_by(HomeworkSubmission.submitted_at.desc())
                .limit(5)
                .all()
            )
            
            report += f"👶 <b>{s.name}</b>:\n"
            if not submissions:
                report += "   Нет оцененных работ.\n"
            else:
                for sub in submissions:
                    hw_title = sub.assignment.homework.title
                    score = sub.score_value
                    max_score = sub.assignment.homework.max_score
                    report += f"   📝 {hw_title}: {score}/{max_score}\n"
            report += "\n"

        await message.answer(report, parse_mode="HTML", reply_markup=PARENT_KB)



async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())