import collections
from ortools.sat.python import cp_model
import pandas as pd # For potential output formatting

# -----------------------------------------------------------------------------
# المرحلة 0: تحميل وإعداد البيانات (سيتم إضافة البيانات الفعلية هنا)
# -----------------------------------------------------------------------------
print("المرحلة 0: جاري تحميل وإعداد البيانات...")

# --- بيانات العينة (للتوضيح فقط - استبدلها ببياناتك الكاملة) ---
# (ملاحظة: تم تبسيط الهياكل قليلاً لتسهيل المعالجة الأولية)
# مثال بيانات المدرسين المحليين
# --- Data for: doctor_local ---
# --- Data for: doctor_local ---

# Example Usage:

# print(Departments[0]['Levels'][0]['LevelName']) # -> المستوى الأول

# print(Departments[0]['Levels'][1]['LevelName']) # -> المستوى الثاني

# print(doctor_local[2]['availability']) # Combined availability for Dr. شكري (ID 16)
# بيانات الأيام والفترات
Days = {d['id']: d['day_name'] for d in [{'id': 1, 'day_name': 'Saturday'}, {'id': 2, 'day_name': 'Sunday'}, {'id': 3, 'day_name': 'Monday'}, {'id': 4, 'day_name': 'Tuesday'}, {'id': 5, 'day_name': 'Wednesday'}, {'id': 6, 'day_name': 'Thursday'}]}
TimeSlots = {ts['id_slot']: (ts['start_timeslot'], ts['end_timeslot']) for ts in [{'id_slot': 1, 'slot_name': 1, 'start_timeslot': '08:00:00', 'end_timeslot': '10:00:00'}, {'id_slot': 2, 'slot_name': 2, 'start_timeslot': '10:00:00', 'end_timeslot': '12:00:00'}, {'id_slot': 3, 'slot_name': 3, 'start_timeslot': '12:00:00', 'end_timeslot': '14:00:00'}, {'id_slot': 4, 'slot_name': 4, 'start_timeslot': '14:00:00', 'end_timeslot': '16:00:00'}]}
day_ids = list(Days.keys())
slot_ids = list(TimeSlots.keys())
num_slots_per_day = len(slot_ids) # Should match availability list length

# بيانات الإعدادات العامة

print("المرحلة 0: اكتملت.")
# -----------------------------------------------------------------------------
# المرحلة 1: تحديد كل جلسات المحاضرات المطلوبة (بناء قائمة الجلسات)
# -----------------------------------------------------------------------------
print("المرحلة 1: جاري تحديد جلسات المحاضرات المطلوبة...")
all_sessions = [] # قائمة بكل جلسة فريدة يجب جدولتها
session_details = {} # قاموس لتخزين تفاصيل كل جلسة

# --- معالجة البيانات لتحديد الجلسات ---
course_info = {c['CourseID']: c for c in Transformed_Courses}

for dept in Departments:
    dept_id = dept['DepartmentID']
    for level in dept['Levels']:
        level_id = level['LevelID']
        # معالجة المقررات النظرية
        for course_data in level['Courses']['Theoretical']:
            course_id = course_data['CourseID']
            groups_count = course_data['GroupsCount']
            c_type = 1 # Theoretical
            linked_practical_id = course_data.get('LinkedPracticalID') # قد يكون None
            for group_num in range(1, groups_count + 1):
                session_key = (dept_id, level_id, course_id, c_type, group_num)
                all_sessions.append(session_key)
                session_details[session_key] = {
                    'dept': dept_id, 'level': level_id, 'course': course_id,
                    'type': c_type, 'group': group_num,
                    'student_count': level['StudentCount'], # العدد الكلي للمستوى
                    'course_name': course_info[course_id]['CourseName'],
                    'linked_practical': linked_practical_id
                }
        # معالجة المقررات العملية
        for course_data in level['Courses']['Practical']:
            course_id = course_data['CourseID']
            groups_count = course_data['GroupsCount']
            c_type = 0 # Practical
            # العدد الكلي للمستوى مقسومًا على عدد المجموعات العملية (تقريب للأعلى إذا لزم الأمر)
            practical_group_size = -(-level['StudentCount'] // groups_count) # Ceiling division
            preferred_rooms = [r['RoomID'] for r in course_data['Rooms']]
            for group_num in range(1, groups_count + 1):
                session_key = (dept_id, level_id, course_id, c_type, group_num)
                all_sessions.append(session_key)
                session_details[session_key] = {
                    'dept': dept_id, 'level': level_id, 'course': course_id,
                    'type': c_type, 'group': group_num,
                    'student_count': practical_group_size, # عدد طلاب المجموعة العملية
                    'course_name': course_info[course_id]['CourseName'],
                    'preferred_rooms': preferred_rooms
                }

print(f"المرحلة 1: تم تحديد {len(all_sessions)} جلسة محاضرة.")

# -----------------------------------------------------------------------------
# المرحلة 2: معرفة الموارد (المدرسون والقاعات) وتحديد المؤهلات والتوفر
# -----------------------------------------------------------------------------
print("المرحلة 2: جاري معالجة الموارد (المدرسون والقاعات)...")

# --- معالجة بيانات المدرسين ---
all_doctors_data = {d['DoctorID']: d for d in doctor_local + doctor_Employ}
course_to_doctors = collections.defaultdict(list)
doctor_courses = collections.defaultdict(list)
doctor_availability_map = {} # Map (doctor_id, day_id, slot_id) -> bool
doctor_required_slots = collections.defaultdict(int)
doctor_is_local_strict = set() # مجموعة الدكاترة المحليين الذين يجب جدولتهم بالكامل في أوقاتهم

# معالجة المؤهلات والتوفر
all_doctor_ids = list(all_doctors_data.keys())
for doc_id, doc_data in all_doctors_data.items():
    # معالجة المقررات التي يدرسها الدكتور
    if 'CourseTaught' in doc_data:
        for taught_info in doc_data['CourseTaught']:
            dept_id = taught_info['DepartmentID']
            # التعامل مع المستويات المتعددة داخل CourseTaught
            if 'Levels' in taught_info:
                 for level_info in taught_info['Levels']:
                    level_id = level_info['LevelID']
                    if 'CoursesID' in level_info:
                        for course_id in level_info['CoursesID']:
                            # نجد نوع المقرر من Transformed_Courses
                            course_type = course_info[course_id]['Type']
                            # نفترض أن كل مجموعة يمكن أن يدرسها الدكتور
                            # (نحتاج لتحديد كل session_key ممكنة للدكتور)
                            possible_sessions = [
                                s for s in all_sessions if s[0] == dept_id and s[1] == level_id and s[2] == course_id
                            ]
                            for session_key in possible_sessions:
                                course_to_doctors[session_key].append(doc_id)
                                if session_key not in doctor_courses[doc_id]:
                                     doctor_courses[doc_id].append(session_key)


    # معالجة التوفر
    # نفترض أن availability موجودة إما مباشرة أو داخل availability_Appointments[0]
    availability = doc_data.get('availability')
    if not availability and 'availability_Appointments' in doc_data and doc_data['availability_Appointments']:
        availability = doc_data['availability_Appointments'][0].get('availability')

    if availability:
        total_available_slots = 0
        for day_name, slots in availability.items():
            day_id = next((id for id, name in Days.items() if name == day_name), None)
            if day_id:
                for i, is_available in enumerate(slots):
                    slot_id = slot_ids[i] # نفترض تطابق ترتيب الفترات
                    doctor_availability_map[(doc_id, day_id, slot_id)] = bool(is_available)
                    if is_available:
                         total_available_slots += 1

    # التعامل مع حالة المدرس المحلي الصارمة
    if doc_id in [d['DoctorID'] for d in doctor_local]:
         required = doc_data.get('Appointments', 0) # عدد المحاضرات المطلوبة
         doctor_required_slots[doc_id] = required
         # اذا كان عدد الفترات المتاحة = عدد الفترات المطلوبة (نفترض محاضرة لكل فترة)
         # هذه حالة تقديرية، قد تحتاج لتعديل بناءً على ساعات المحاضرة الفعلية
         if total_available_slots > 0 and total_available_slots == required:
              doctor_is_local_strict.add(doc_id)
              print(f"  - تنبيه: الدكتور المحلي {doc_data['DoctorName']} ({doc_id}) لديه حالة توفر صارمة.")


# --- معالجة بيانات القاعات ---
all_room_data = {r['RoomID']: r for r in Rooms}
room_availability_map = {} # Map (room_id, day_id, slot_id) -> bool
rooms_by_type = {0: [], 1: []} # 0: Practical, 1: Theoretical

for room_id, room_data in all_room_data.items():
    rooms_by_type[room_data['Type']].append(room_id)
    availability = room_data.get('Availability')
    if availability:
        for day_name, slots in availability.items():
            day_id = next((id for id, name in Days.items() if name == day_name), None)
            if day_id:
                for i, is_available in enumerate(slots):
                    slot_id = slot_ids[i]
                    room_availability_map[(room_id, day_id, slot_id)] = bool(is_available)

all_room_ids = list(all_room_data.keys())
print("المرحلة 2: اكتملت.")

# -----------------------------------------------------------------------------
# المرحلة 3: بناء نموذج CP-SAT وتعريف المتغيرات
# -----------------------------------------------------------------------------
# -----------------------------------------------------------------------------
# المرحلة 3: بناء نموذج CP-SAT وتعريف المتغيرات
# -----------------------------------------------------------------------------
print("المرحلة 3: جاري بناء نموذج CP-SAT وتعريف المتغيرات...")
model = cp_model.CpModel()

# --- متغيرات القرار الأساسية ---
# هل الجلسة session مُجدولة في اليوم day، الفترة slot، القاعة room، بواسطة الدكتور doctor؟
assignments = {}

for session_key in all_sessions:
    # استخراج تفاصيل مفتاح الجلسة
    dept_id, level_id, course_id, course_type, group_num = session_key

    # الحصول على قائمة المدرسين المحتملين لهذه الجلسة
    possible_doctors = course_to_doctors.get(session_key, []) # استخدم .get لتجنب الخطأ إذا لم يكن هناك مدرسون

    # --- التحقق الأولي: هل يوجد مدرسون مؤهلون؟ ---
    if not possible_doctors:
        print(f"تحذير: لا يوجد مدرس مؤهل للجلسة {session_key} ({session_details[session_key]['course_name']}). سيتم تجاهلها.")
        continue # انتقل إلى الجلسة التالية

    # الحصول على تفاصيل الجلسة (تحتوي على preferred_rooms للعملي)
    # يجب التأكد من أن session_details تم تعبئتها بشكل صحيح في المرحلة 1
    details = session_details.get(session_key)
    if not details:
         print(f"تحذير: لم يتم العثور على تفاصيل للجلسة {session_key}. سيتم تجاهلها.")
         continue # انتقل إلى الجلسة التالية

    # تحديد قائمة القاعات المبدئية بناءً على نوع المقرر (نظري/عملي)
    possible_initial_rooms = rooms_by_type.get(course_type, [])

    # --- التحقق الأولي: هل هناك قاعات من النوع المناسب؟ ---
    if not possible_initial_rooms:
        print(f"تحذير: لا توجد قاعات متاحة من النوع {course_type} للجلسة {session_key} ({details['course_name']}). سيتم تجاهلها.")
        continue # انتقل إلى الجلسة التالية

    # تحديد قائمة القاعات المسموحة بشكل نهائي (خاصة للعملي)
    allowed_room_ids = []
    if course_type == 0: # مقرر عملي
        preferred = details.get('preferred_rooms', [])
        if not preferred:
             print(f"تحذير: المقرر العملي {session_key} ({details['course_name']}) ليس لديه قاعات مفضلة محددة. سيتم تجاهله.")
             continue # لا يمكن جدولة عملي بدون قاعة محددة
        # للقاعات العملية، القائمة المسموحة هي فقط القاعات المفضلة
        allowed_room_ids = preferred
    else: # مقرر نظري
        # للقاعات النظرية، القائمة المسموحة مبدئياً هي كل القاعات النظرية
        allowed_room_ids = possible_initial_rooms

    # --- البدء بحلقات الأيام والفترات والقاعات والمدرسين لإنشاء المتغيرات ---
    for day_id in day_ids:
        for slot_id in slot_ids:
            # المرور فقط على القاعات المسموحة بشكل نهائي لهذه الجلسة
            for room_id in allowed_room_ids:

                # التحقق 1: هل القاعة المسموحة هي ضمن قائمة القاعات المبدئية (فحص سلامة إضافي)؟
                # هذا التحقق قد لا يكون ضرورياً إذا كان المنطق أعلاه صحيحًا ولكنه لا يضر
                if room_id not in possible_initial_rooms:
                    continue # هذه القاعة ليست من النوع الصحيح أصلاً

                # التحقق 2: هل القاعة متاحة في هذا اليوم وهذه الفترة؟
                if not room_availability_map.get((room_id, day_id, slot_id), False):
                    continue # القاعة غير متاحة في هذا الوقت

                # التحقق 3 (مدمج الآن في allowed_room_ids):
                # (لم يعد هناك حاجة للتحقق مرة أخرى إذا كان المقرر عمليًا والقاعة مسموحة،
                # لأننا نمر فقط على allowed_room_ids التي تم فلترتها مسبقًا للعملي)

                # الآن، المرور على المدرسين المحتملين
                for doctor_id in possible_doctors:
                    # التحقق 4: هل المدرس متاح في هذا اليوم وهذه الفترة؟
                    if not doctor_availability_map.get((doctor_id, day_id, slot_id), False):
                        continue # المدرس غير متاح في هذا الوقت

                    # --- *** إذا وصلت إلى هنا، فهذه التركيبة (جلسة، يوم، فترة، قاعة، مدرس) صالحة وممكنة *** ---
                    # --- إنشاء المتغير البولياني للقرار ---
                    var_key = (session_key, day_id, slot_id, room_id, doctor_id)
                    var_name = f'assign_S{session_key}_D{day_id}_T{slot_id}_R{room_id}_P{doctor_id}'
                    # تقصير اسم المتغير إذا كان طويلاً جدًا (اختياري)
                    # var_name = f'a_{session_key[2]}_{session_key[4]}_{day_id}_{slot_id}_{room_id}_{doctor_id}'
                    assignments[var_key] = model.NewBoolVar(var_name)

# --- نهاية حلقات إنشاء المتغيرات ---

print(f"المرحلة 3: تم تعريف {len(assignments)} متغير قرار محتمل.")
# -----------------------------------------------------------------------------
# نهاية المرحلة 3
# -----------------------------------------------------------------------------# -----------------------------------------------------------------------------
# المرحلة 4: إضافة القيود (الصلبة والمرنة) ودالة الهدف
# -----------------------------------------------------------------------------
print("المرحلة 4: جاري إضافة القيود ودالة الهدف...")
# --- (الكود التالي يوضع ضمن القيود الصلبة في المرحلة 4) ---
# --- (نهاية كود القيد) ---
# --- قائمة لتجميع أجزاء دالة الهدف (للقيود المرنة) ---
objective_terms = []
penalty_weights = {
    "MIN_LECTURES_DEPT": 50,
    "MIN_LECTURES_PROF": 50,
    "MAX_LECTURES_DEPT": 100, # عقوبة أعلى للتجاوز
    "MAX_LECTURES_PROF": 100,
    "PROF_GAP": 10,
    "DEPT_GAP": 10,
    "LEVEL_SPREAD_DAYS": 20,
    "ROOM_CHANGE": 5,
    "SINGLE_LECTURE_DAY_PROF": 30,
    "SINGLE_LECTURE_DAY_DEPT": 30,
    "LOCAL_STRICT_VIOLATION": 1000 # عقوبة عالية جدًا لانتهاك حالة المدرس المحلي الصارم
}
# --- (الكود التالي يوضع في بداية المرحلة 4، قبل حلقات القيود) ---
print("   - تجهيز بيانات عدد المجموعات للمقررات...")
course_group_count = {} # Map: (dept_id, level_id, course_id) -> group_count
all_dept_level_keys = set() # لتجميع مفاتيح القسم والمستوى الموجودة

for dept in Departments:
    dept_id = dept['DepartmentID']
    for level in dept['Levels']:
        level_id = level['LevelID']
        all_dept_level_keys.add((dept_id, level_id)) # تخزين التركيبة الموجودة

        # معالجة المقررات النظرية
        for course_data in level['Courses']['Theoretical']:
            course_id = course_data['CourseID']
            groups_count = course_data['GroupsCount']
            course_group_count[(dept_id, level_id, course_id)] = groups_count

        # معالجة المقررات العملية
        for course_data in level['Courses']['Practical']:
            course_id = course_data['CourseID']
            groups_count = course_data['GroupsCount']
            course_group_count[(dept_id, level_id, course_id)] = groups_count

print("   - اكتمل تجهيز بيانات عدد المجموعات.")
# --- (نهاية كود التجهيز) ---
# --- 4.1: القيود الصلبة (Hard Constraints) ---
print("  - إضافة القيود الصلبة...")
# --- (الكود التالي يوضع ضمن القيود الصلبة في المرحلة 4) ---
print("   - إضافة قيد عدم الحجز المزدوج للقاعات...")

# استخدام مجموعة لتتبع المفاتيح التي تم معالجتها لتجنب إضافة نفس القيد عدة مرات
processed_room_slots = set()

for var_key in assignments.keys():
    session_key, day_id, slot_id, room_id, doctor_id = var_key
    # dept_id, level_id, course_id, course_type, group_num = session_key # لسنا بحاجة لهذه الآن

    # القيد: عدم حجز القاعة مرتين في نفس الوقت
    room_time_key = (room_id, day_id, slot_id)
    if room_time_key not in processed_room_slots:
        # اجمع كل متغيرات الجدولة التي تستخدم هذه القاعة في هذا الوقت المحدد
        conflicting_room_assignments = [
            v for k, v in assignments.items() if
            k[3] == room_id and  # نفس القاعة
            k[1] == day_id and   # نفس اليوم
            k[2] == slot_id      # نفس الفترة
        ]
        # تأكد من وجود متغيرات لإضافة القيد (إذا كانت القائمة غير فارغة)
        if conflicting_room_assignments:
             model.Add(sum(conflicting_room_assignments) <= 1)

        # ضع علامة بأنه تم معالجة هذه الخانة الزمنية للقاعة بغض النظر عن وجود متغيرات لها
        # هذا يمنع إعادة التحقق غير الضروري
        processed_room_slots.add(room_time_key)

print("   - اكتملت إضافة قيد عدم الحجز المزدوج للقاعات.")
# --- (نهاية كود القيد) ---
# القيد 1: كل جلسة يجب أن تُجدول مرة واحدة بالضبط
sessions_processed_hc1 = set()
for var_key in assignments.keys():
     session_key = var_key[0]
     if session_key not in sessions_processed_hc1:
          # التأكد أن هناك متغيرات معرفة لهذه الجلسة
          possible_assignments_for_session = [v for k, v in assignments.items() if k[0] == session_key]
          if possible_assignments_for_session:
               model.Add(sum(possible_assignments_for_session) == 1)
               sessions_processed_hc1.add(session_key)
# --- (الكود التالي يوضع ضمن القيود الصلبة في المرحلة 4) ---
print("   - إضافة قيد تطابق عدد المجموعات للمقررات المتعددة المجموعات المتزامنة...")

# المرور على كل قسم ومستوى ويوم وفترة زمنية
# all_dept_level_keys تم تعريفه سابقاً: set([(dept_id, level_id), ...])
# course_group_count تم تعريفه سابقاً: map {(dept_id, level_id, course_id): group_count}

for dept_id, level_id in all_dept_level_keys:
    # 1. تحديد المقررات متعددة المجموعات لهذا المستوى
    multi_group_courses_in_level = []
    for (d, l, c_id), g_count in course_group_count.items():
        if d == dept_id and l == level_id and g_count > 1:
            multi_group_courses_in_level.append(c_id)

    # لا حاجة للقيد إذا لم يكن هناك مقررين متعددين المجموعات على الأقل في هذا المستوى
    if len(multi_group_courses_in_level) < 2:
        continue

    # 2. المرور على الأيام والفترات
    for day_id in day_ids:
        for slot_id in slot_ids:

            # 3. لكل مقرر متعدد المجموعات، تحديد ما إذا كان مجدولاً في هذا الوقت
            is_multi_group_course_scheduled = {} # Map: course_id -> BoolVar indicator
            for course_id in multi_group_courses_in_level:
                indicator = model.NewBoolVar(f'mgsched_{dept_id}_{level_id}_{day_id}_{slot_id}_{course_id}')
                is_multi_group_course_scheduled[course_id] = indicator

                # البحث عن أي متغير جدولة لهذا المقرر/المستوى/الوقت
                assignments_for_course_slot = [
                    v for k, v in assignments.items() if
                    k[0][0] == dept_id and   # نفس القسم
                    k[0][1] == level_id and   # نفس المستوى
                    k[0][2] == course_id and  # نفس المقرر
                    k[1] == day_id and        # نفس اليوم
                    k[2] == slot_id           # نفس الفترة
                ]

                # ربط المتغير المؤشر: يكون صحيحًا إذا تم جدولة أي مجموعة لهذا المقرر في هذا الوقت
                if assignments_for_course_slot:
                    # نستخدم Sum >= 1 لأن أكثر من مجموعة قد تُجدوَل (نظريًا)
                    model.Add(sum(assignments_for_course_slot) >= 1).OnlyEnforceIf(indicator)
                    model.Add(sum(assignments_for_course_slot) == 0).OnlyEnforceIf(indicator.Not())
                else:
                    # إذا لم تكن هناك متغيرات جدولة ممكنة أصلاً لهذا المقرر في هذا الوقت
                    model.Add(indicator == 0)

            # 4. إضافة القيد: لا يمكن جدولة مقررين متعددين المجموعات لهما عدد مجموعات مختلف في نفس الوقت
            # المرور على أزواج المقررات متعددة المجموعات
            for i in range(len(multi_group_courses_in_level)):
                for j in range(i + 1, len(multi_group_courses_in_level)):
                    c1_id = multi_group_courses_in_level[i]
                    c2_id = multi_group_courses_in_level[j]

                    # الحصول على عدد المجموعات الكلي لكل مقرر
                    g_count1 = course_group_count.get((dept_id, level_id, c1_id))
                    g_count2 = course_group_count.get((dept_id, level_id, c2_id))

                    # إذا كان عدد المجموعات الكلي مختلفًا
                    if g_count1 is not None and g_count2 is not None and g_count1 != g_count2:
                        # لا يمكن أن يكون كلا المقررين مجدولين في نفس الوقت
                        # الحصول على متغيرات المؤشر الخاصة بهما لهذا الوقت
                        indicator1 = is_multi_group_course_scheduled[c1_id]
                        indicator2 = is_multi_group_course_scheduled[c2_id]

                        # القيد: على الأكثر واحد منهما يمكن أن يكون صحيحًا (مجدولاً)
                        # AddBoolOr([indicator1.Not(), indicator2.Not()])
                        model.Add(indicator1 + indicator2 <= 1)


print("   - اكتملت إضافة قيد تطابق عدد المجموعات للمقررات المتعددة المجموعات المتزامنة.")
# --- (نهاية كود القيد) ---
# القيد 2: لا للحجوزات المزدوجة (قاعة، مدرس، مجموعة طلاب)
processed_slots = set()
for var_key in assignments.keys():
    session_key, day_id, slot_id, room_id, doctor_id = var_key
    dept_id, level_id, course_id, course_type, group_num = session_key
    student_group_key = (dept_id, level_id, group_num, course_type) # مفتاح لتعريف مجموعة الطلاب الفريدة

    slot_time_key = (day_id, slot_id)

    # قاعة في وقت معين
    room_time_key = (room_id, day_id, slot_id)
    if room_time_key not in processed_slots:
        model.Add(sum(assignments[k] for k in assignments if k[1] == day_id and k[2] == slot_id and k[3] == room_id) <= 1)
        processed_slots.add(room_time_key)

    # مدرس في وقت معين
    doctor_time_key = (doctor_id, day_id, slot_id)
    if doctor_time_key not in processed_slots:
        model.Add(sum(assignments[k] for k in assignments if k[1] == day_id and k[2] == slot_id and k[4] == doctor_id) <= 1)
        processed_slots.add(doctor_time_key)

    # مجموعة طلاب في وقت معين (الأكثر تعقيدًا)
    # نحتاج لتجميع كل الجلسات التي تخص نفس مجموعة الطلاب (قسم، مستوى، رقم مجموعة)
    group_time_key = (student_group_key, day_id, slot_id)
    if group_time_key not in processed_slots:
        sessions_for_group = [
            s_key for s_key in all_sessions if
            s_key[0] == dept_id and s_key[1] == level_id and s_key[4] == group_num
        ]
        model.Add(sum(assignments[k] for k in assignments if k[0] in sessions_for_group and k[1] == day_id and k[2] == slot_id) <= 1)
        processed_slots.add(group_time_key)

# --- (الكود التالي يوضع ضمن القيود الصلبة في المرحلة 4) ---
print("   - إضافة قيد منع تعارض المقررات ذات المجموعة الواحدة مع متعددة المجموعات...")

# المرور على كل قسم ومستوى ويوم وفترة زمنية
for dept_id, level_id in all_dept_level_keys: # استخدم المفاتيح التي جمعناها
    for day_id in day_ids:
        for slot_id in slot_ids:

            single_group_assignments_in_slot = []
            multi_group_assignments_in_slot = []

            # البحث عن كل متغيرات الجدولة المحتملة لهذا القسم/المستوى/الوقت
            # وتصنيفها حسب عدد المجموعات
            for var_key, var_value in assignments.items():
                session_key, d, s, r, doc = var_key

                # التحقق مما إذا كان المتغير يخص هذا القسم/المستوى/اليوم/الفترة
                if session_key[0] == dept_id and session_key[1] == level_id and d == day_id and s == slot_id:
                    course_id = session_key[2]
                    lookup_key = (dept_id, level_id, course_id)

                    # الحصول على عدد المجموعات من القاموس الذي جهزناه
                    # قد يكون المقرر غير موجود في القاموس إذا لم يكن له بيانات مجموعات (نادر)
                    groups_count = course_group_count.get(lookup_key)

                    if groups_count is not None:
                        if groups_count == 1:
                            single_group_assignments_in_slot.append(var_value)
                        elif groups_count > 1:
                            multi_group_assignments_in_slot.append(var_value)
                    # else:
                        # يمكنك إضافة تحذير هنا إذا كان المقرر غير موجود في قاموس عدد المجموعات
                        # print(f"Warning: Could not find group count for {lookup_key}")


            # تعريف المتغيرات البوليانية المساعدة
            is_single_scheduled = model.NewBoolVar(f'single_sch_{dept_id}_{level_id}_{day_id}_{slot_id}')
            is_multi_scheduled = model.NewBoolVar(f'multi_sch_{dept_id}_{level_id}_{day_id}_{slot_id}')

            # ربط المتغيرات المساعدة بمجموع متغيرات الجدولة
            # إذا لم يكن هناك متغيرات محتملة لهذا النوع في هذا الوقت، فقيمة المساعد ستكون False
            if single_group_assignments_in_slot:
                model.Add(sum(single_group_assignments_in_slot) >= 1).OnlyEnforceIf(is_single_scheduled)
                model.Add(sum(single_group_assignments_in_slot) == 0).OnlyEnforceIf(is_single_scheduled.Not())
            else:
                model.Add(is_single_scheduled == 0) # لا يمكن جدولته إذا لم يكن هناك متغيرات

            if multi_group_assignments_in_slot:
                # ملاحظة: قد يكون المجموع > 1 إذا سمحت بجدولة مجموعتين متعددتين بالتوازي
                # لذلك نستخدم >= 1 للربط
                model.Add(sum(multi_group_assignments_in_slot) >= 1).OnlyEnforceIf(is_multi_scheduled)
                model.Add(sum(multi_group_assignments_in_slot) == 0).OnlyEnforceIf(is_multi_scheduled.Not())
            else:
                model.Add(is_multi_scheduled == 0) # لا يمكن جدولته إذا لم يكن هناك متغيرات

            # القيد الأساسي: لا يمكن أن يكون كلا النوعين مجدولاً في نفس الوقت
            model.Add(is_single_scheduled + is_multi_scheduled <= 1)

print("   - اكتملت إضافة قيد منع التعارض بين أنواع المجموعات.")
# --- (نهاية كود القيد) ---
# القيد 3: حالة المدرس المحلي الصارم (N_available == N_required)
# (تم تضمين جزء منه في المرحلة 2، الآن نضيف القيد الفعلي)
local_strict_violation_vars = []
for doctor_id in doctor_is_local_strict:
    # كل فترة متاحة يجب أن تُستخدم لمحاضرة لهذا الدكتور
    for day_id in day_ids:
         for slot_id in slot_ids:
              if doctor_availability_map.get((doctor_id, day_id, slot_id), False):
                   # يجب أن يكون هناك محاضرة مجدولة لهذا الدكتور في هذا الوقت
                   sessions_in_slot = [
                       assignments[k] for k in assignments if k[1] == day_id and k[2] == slot_id and k[4] == doctor_id
                   ]
                   if sessions_in_slot: # تأكد أن هناك متغيرات محتملة
                        # هذا قيد صلب تقريبًا، لكن نضيف متغير انتهاك بعقوبة عالية
                        slot_must_be_used = model.NewBoolVar(f'local_strict_{doctor_id}_{day_id}_{slot_id}')
                        model.Add(sum(sessions_in_slot) == slot_must_be_used)
                        # نعاقب إذا لم يتم استخدام الفترة (slot_must_be_used == 0)
                        # نضيف (1 - slot_must_be_used) للهدف
                        violation_expr = 1 - slot_must_be_used
                        objective_terms.append(violation_expr * penalty_weights["LOCAL_STRICT_VIOLATION"])
                   #else:
                        # This case shouldn't happen if variables were created correctly based on availability
                        # print(f"Warning: No assignable variables for strict local doctor {doctor_id} at available slot ({day_id}, {slot_id})")

# القيد 4: (اختياري صلب) ربط المقرر النظري بالعملي المرتبط به
# يمكن إضافة قيد أن المحاضرة العملية لا تحدث قبل النظرية في نفس الأسبوع (أو اليوم)
# هذا يتطلب تعريف علاقة بين متغيرات الجدولة وهو أكثر تعقيدًا، سنتركه كقيد مرن أو نتجاهله الآن.

# --- (تعديل ضمن القيد الصلب: "منع تعارض المقررات ذات المجموعة الواحدة...") ---
# تأكد من تعريف هذه القواميس قبل الحلقات التي تنشئ المتغيرات
single_sched_vars = {} # Map: (dept, level, day, slot) -> BoolVar
multi_sched_vars = {}  # Map: (dept, level, day, slot) -> BoolVar

# ... داخل حلقات dept_id, level_id, day_id, slot_id ...
# بعد حساب single_group_assignments_in_slot و multi_group_assignments_in_slot

# تعريف وتخزين المتغيرات المساعدة
time_key = (dept_id, level_id, day_id, slot_id)
is_single_scheduled = model.NewBoolVar(f'single_sch_{dept_id}_{level_id}_{day_id}_{slot_id}')
is_multi_scheduled = model.NewBoolVar(f'multi_sch_{dept_id}_{level_id}_{day_id}_{slot_id}')
single_sched_vars[time_key] = is_single_scheduled
multi_sched_vars[time_key] = is_multi_scheduled

# ... باقي منطق ربط المتغيرات بالمجموع وإضافة القيد الصلب ...
# model.Add(is_single_scheduled + is_multi_scheduled <= 1)
# --- (نهاية التعديل في القيد الصلب) ---
# --- 4.2: القيود المرنة (Soft Constraints) ---
print("  - إضافة القيود المرنة (كدالة هدف)...")

# هدف 1 & 2: توازن المحاضرات اليومية (الحد الأدنى والأقصى)
# --- تعديل الأسطر المسببة للخطأ ---
# --- (الكود التالي يوضع ضمن القيود المرنة في المرحلة 4، مع objective_terms) ---
print("  - إضافة هدف تقليل الفجوات الزمنية للمجموعات الطلابية المحددة...")

# 1. تجميع متغيرات الجدولة حسب المجموعة الطلابية الفعلية
#    نحتاج طريقة لتعريف كل "وحدة حضور" فريدة من الطلاب.
assignments_by_student_group = collections.defaultdict(list)
all_student_group_keys = set() # لتتبع المفاتيح الفريدة للمجموعات

# التأكد من أن course_group_count معرفة ومتاحة هنا (عادة في بداية المرحلة 4)
# course_group_count = map {(dept_id, level_id, course_id): group_count}

for var_key, var_value in assignments.items():
    session_key, day_id, slot_id, room_id, doctor_id = var_key
    dept_id, level_id, course_id, course_type, group_num = session_key
    lookup_key = (dept_id, level_id, course_id)

    # الحصول على عدد المجموعات الكلي للمقرر لتحديد نوع المجموعة الطلابية
    total_groups_for_course = course_group_count.get(lookup_key, 1) # افتراض 1 إذا لم يوجد

    student_group_key = None
    if total_groups_for_course == 1:
        # المحاضرات التي يحضرها المستوى بأكمله (نظري أو عملي لمجموعة واحدة)
        student_group_key = (dept_id, level_id, 'level_wide') # نستخدم معرف خاص
    elif total_groups_for_course > 1:
         # المقررات متعددة المجموعات (عادة عملية، أو نظرية مقسمة)
         # مفتاح المجموعة الطلابية هنا هو رقم المجموعة المحدد
         student_group_key = (dept_id, level_id, group_num)
    else:
         # حالة غير متوقعة
         print(f"تحذير: عدد مجموعات غير صالح {total_groups_for_course} للمقرر {lookup_key}")
         continue

    if student_group_key:
        # نضيف متغير الجدولة وقيده الزمني إلى قائمة هذه المجموعة الطلابية
        assignments_by_student_group[student_group_key].append((day_id, slot_id, var_value))
        all_student_group_keys.add(student_group_key)

# 2. إضافة عقوبة الفجوات لكل مجموعة طلابية ولكل يوم
#    استخدم وزن عقوبة جديد أو موجود من penalty_weights
STUDENT_GROUP_GAP_PENALTY_WEIGHT = penalty_weights.get("STUDENT_GROUP_GAP", 10) # مثال لوزن العقوبة

# slot_ids يجب أن تكون مرتبة زمنياً (وهي كذلك في بياناتك)
sorted_slot_ids = sorted(slot_ids) # ضمان الترتيب للاعتماد على الفهرس

for group_key in all_student_group_keys:
    dept_id, level_id, group_identifier = group_key
    group_str = f"{dept_id}_{level_id}_{group_identifier}" # لأسماء المتغيرات الفريدة

    for day_id in day_ids:
        # متغيرات مساعدة لتتبع وجود محاضرة لهذه المجموعة في كل فترة
        lecture_in_slot = {}
        possible_lectures_exist_on_day = False # لتجنب إضافة قيود لا داعي لها

        for slot_id in sorted_slot_ids:
            slot_var = model.NewBoolVar(f'sgrp_{group_str}_day_{day_id}_slot_{slot_id}_has_lect')
            lecture_in_slot[slot_id] = slot_var

            # البحث عن متغيرات الجدولة لهذه المجموعة في هذا اليوم وهذه الفترة
            assignments_for_group_in_this_slot = [
                var for d, s, var in assignments_by_student_group[group_key] if d == day_id and s == slot_id
            ]

            if assignments_for_group_in_this_slot:
                possible_lectures_exist_on_day = True
                # ربط المتغير المساعد: صحيح إذا كانت هناك محاضرة واحدة على الأقل مجدولة
                model.Add(sum(assignments_for_group_in_this_slot) >= 1).OnlyEnforceIf(slot_var)
                model.Add(sum(assignments_for_group_in_this_slot) == 0).OnlyEnforceIf(slot_var.Not())
            else:
                # لا توجد متغيرات جدولة ممكنة لهذه المجموعة في هذا الوقت
                model.Add(slot_var == 0)

        # إذا لم تكن هناك أي محاضرات محتملة لهذه المجموعة في هذا اليوم، فلا يمكن أن تكون هناك فجوات
        if not possible_lectures_exist_on_day:
            continue

        # 3. البحث عن فجوات (محاضرة، فراغ، محاضرة) عبر الفترات المتتالية
        num_slots = len(sorted_slot_ids)
        if num_slots >= 3: # نحتاج 3 فترات على الأقل لاكتشاف فجوة بسعة فترة واحدة
            for i in range(num_slots - 2):
                s1 = sorted_slot_ids[i]
                s2 = sorted_slot_ids[i+1] # الفترة الوسطى (المحتمل أن تكون فجوة)
                s3 = sorted_slot_ids[i+2]

                # متغير يشير إلى وجود فجوة في الفترة s2
                gap_detected_at_s2 = model.NewBoolVar(f'gap_sgrp_{group_str}_day_{day_id}_slot_{s2}')

                # الفجوة تحدث إذا: محاضرة في s1، لا محاضرة في s2، محاضرة في s3
                # نستخدم متغيرات lecture_in_slot التي تم ربطها سابقًا
                model.AddBoolAnd([
                    lecture_in_slot[s1],
                    lecture_in_slot[s2].Not(), # النفي هنا يعني وجود فجوة
                    lecture_in_slot[s3]
                ]).OnlyEnforceIf(gap_detected_at_s2)

                # إذا لم تتحقق الشروط الثلاثة، يجب أن يكون gap_detected_at_s2 خطأ.
                # هذا يحدث ضمنيًا لأن الهدف هو تقليل المتغيرات التي تساهم في العقوبة.
                # يمكن إضافة قيد صريح إذا لزم الأمر، لكنه عادة غير مطلوب مع Minimize.
                # model.AddImplication(gap_detected_at_s2.Not(), BoolOr([lecture_in_slot[s1].Not(), lecture_in_slot[s2], lecture_in_slot[s3].Not()]))


                # إضافة عقوبة الفجوة إلى دالة الهدف
                objective_terms.append(gap_detected_at_s2 * STUDENT_GROUP_GAP_PENALTY_WEIGHT)

        # يمكن توسيع هذا ليشمل فجوات أكبر (مثل محاضرة، فراغ، فراغ، محاضرة) إذا لزم الأمر
        # مثال لفجوة من فترتين (بين s1 و s4):
        # if num_slots >= 4:
        #     for i in range(num_slots - 3):
        #         s1 = sorted_slot_ids[i]
        #         s2 = sorted_slot_ids[i+1]
        #         s3 = sorted_slot_ids[i+2]
        #         s4 = sorted_slot_ids[i+3]
        #         gap_2slots_detected = model.NewBoolVar(f'gap2_sgrp_{group_str}_day_{day_id}_slot_{s2}_{s3}')
        #         model.AddBoolAnd([
        #             lecture_in_slot[s1],
        #             lecture_in_slot[s2].Not(),
        #             lecture_in_slot[s3].Not(),
        #             lecture_in_slot[s4]
        #         ]).OnlyEnforceIf(gap_2slots_detected)
        #         objective_terms.append(gap_2slots_detected * STUDENT_GROUP_GAP_PENALTY_WEIGHT * 1.5) # عقوبة أعلى لفجوة أطول


print("  - اكتملت إضافة هدف تقليل الفجوات الزمنية للمجموعات الطلابية.")
# --- (نهاية كود القيد المرن) ---
# هدف 1 & 2: توازن المحاضرات اليومية (الحد الأدنى والأقصى)
max_dept_lect = GeneralSettings[0]['max_lectures_per_day_department'] # أضفنا [0]
min_dept_lect = GeneralSettings[0]['min_lectures_per_day_department'] # أضفنا [0]
max_prof_lect = GeneralSettings[0]['max_lectures_per_day_professor'] # أضفنا [0]
min_prof_lect = GeneralSettings[0]['min_lectures_per_day_professor'] # أضفنا [0]

# ... باقي الكود ...
# للمستويات
dept_level_keys = set([(s[0], s[1]) for s in all_sessions])
for dept_id, level_id in dept_level_keys:
    for day_id in day_ids:
        lectures_on_day = []
        for k, v in assignments.items():
             session_key, d, s, r, doc = k
             if d == day_id and session_key[0] == dept_id and session_key[1] == level_id:
                  lectures_on_day.append(v)

        if not lectures_on_day: continue # لا يوجد محاضرات محتملة لهذا المستوى في هذا اليوم

        lectures_count = sum(lectures_on_day)

        # عقوبة لتجاوز الحد الأقصى
        over_max_dept = model.NewBoolVar(f'over_max_dept_{dept_id}_{level_id}_{day_id}')
        model.Add(lectures_count > max_dept_lect).OnlyEnforceIf(over_max_dept)
        model.Add(lectures_count <= max_dept_lect).OnlyEnforceIf(over_max_dept.Not())
        objective_terms.append(over_max_dept * penalty_weights["MAX_LECTURES_DEPT"])

        # عقوبة لكون العدد أقل من الحد الأدنى (باستثناء 0)
        under_min_dept = model.NewBoolVar(f'under_min_dept_{dept_id}_{level_id}_{day_id}')
        model.Add(lectures_count < min_dept_lect).OnlyEnforceIf(under_min_dept)
        model.Add(lectures_count >= min_dept_lect).OnlyEnforceIf(under_min_dept.Not())
        # لا نعاقب إذا كان العدد 0
        non_zero_dept = model.NewBoolVar(f'non_zero_dept_{dept_id}_{level_id}_{day_id}')
        model.Add(lectures_count > 0).OnlyEnforceIf(non_zero_dept)
        model.Add(lectures_count == 0).OnlyEnforceIf(non_zero_dept.Not())

        actual_under_min_penalty_dept = model.NewBoolVar(f'actual_under_min_dept_{dept_id}_{level_id}_{day_id}')
        model.AddBoolAnd([under_min_dept, non_zero_dept]).OnlyEnforceIf(actual_under_min_penalty_dept)
        model.AddImplication(actual_under_min_penalty_dept, under_min_dept) # Ensure if penalty applies, the condition holds
        model.AddImplication(actual_under_min_penalty_dept, non_zero_dept) # Ensure if penalty applies, the condition holds

        objective_terms.append(actual_under_min_penalty_dept * penalty_weights["MIN_LECTURES_DEPT"])


# للمدرسين (مع استثناء المحلي الصارم من عقوبة الحد الأدنى)
for doctor_id in all_doctor_ids:
     is_strict = doctor_id in doctor_is_local_strict
     for day_id in day_ids:
        lectures_on_day = [v for k, v in assignments.items() if k[1] == day_id and k[4] == doctor_id]

        if not lectures_on_day: continue

        lectures_count = sum(lectures_on_day)

        # عقوبة لتجاوز الحد الأقصى
        over_max_prof = model.NewBoolVar(f'over_max_prof_{doctor_id}_{day_id}')
        model.Add(lectures_count > max_prof_lect).OnlyEnforceIf(over_max_prof)
        model.Add(lectures_count <= max_prof_lect).OnlyEnforceIf(over_max_prof.Not())
        objective_terms.append(over_max_prof * penalty_weights["MAX_LECTURES_PROF"])

        # عقوبة لكون العدد أقل من الحد الأدنى (باستثناء 0 والصارم)
        if not is_strict:
             under_min_prof = model.NewBoolVar(f'under_min_prof_{doctor_id}_{day_id}')
             model.Add(lectures_count < min_prof_lect).OnlyEnforceIf(under_min_prof)
             model.Add(lectures_count >= min_prof_lect).OnlyEnforceIf(under_min_prof.Not())

             non_zero_prof = model.NewBoolVar(f'non_zero_prof_{doctor_id}_{day_id}')
             model.Add(lectures_count > 0).OnlyEnforceIf(non_zero_prof)
             model.Add(lectures_count == 0).OnlyEnforceIf(non_zero_prof.Not())

             actual_under_min_penalty_prof = model.NewBoolVar(f'actual_under_min_prof_{doctor_id}_{day_id}')
             model.AddBoolAnd([under_min_prof, non_zero_prof]).OnlyEnforceIf(actual_under_min_penalty_prof)
             model.AddImplication(actual_under_min_penalty_prof, under_min_prof)
             model.AddImplication(actual_under_min_penalty_prof, non_zero_prof)

             objective_terms.append(actual_under_min_penalty_prof * penalty_weights["MIN_LECTURES_PROF"])
# --- (الكود التالي يوضع ضمن القيود المرنة في المرحلة 4، مع objective_terms) ---
print("  - إضافة هدف معاقبة الانتقال المباشر من محاضرة مجموعة إلى محاضرة مستوى...")

# استخدم وزنًا عاليًا لهذه العقوبة لأنها تسبب فجوات مؤكدة
GROUP_TO_LEVEL_TRANSITION_PENALTY_WEIGHT = penalty_weights.get("GROUP_LEVEL_TRANSITION", 75) # مثال لوزن عالٍ

sorted_slot_ids = sorted(slot_ids)

for dept_id, level_id in all_dept_level_keys:
    for day_id in day_ids:
        # المرور على الفترات المتجاورة (سننظر إلى الفترة السابقة s_prev والفترة الحالية s_curr)
        for i in range(1, len(sorted_slot_ids)): # نبدأ من الفترة الثانية
            s_prev_id = sorted_slot_ids[i-1]
            s_curr_id = sorted_slot_ids[i]

            key_prev = (dept_id, level_id, day_id, s_prev_id)
            key_curr = (dept_id, level_id, day_id, s_curr_id)

            # الحصول على متغيرات المؤشر المخزنة
            # هل كانت هناك محاضرة مجموعة فرعية في الفترة السابقة؟
            group_specific_in_prev = multi_sched_vars.get(key_prev)
            # هل هناك محاضرة مستوى ككل في الفترة الحالية؟
            level_wide_in_curr = single_sched_vars.get(key_curr)

            # تحقق من وجود المتغيرات اللازمة
            if all([group_specific_in_prev, level_wide_in_curr]):

                # متغير للإشارة إلى حدوث هذا الانتقال غير المرغوب فيه
                undesired_group_to_level_transition = model.NewBoolVar(f'pen_g2l_{dept_id}_{level_id}_{day_id}_{s_curr_id}')

                # الانتقال يحدث إذا group_specific_in_prev صحيح و level_wide_in_curr صحيح
                model.AddBoolAnd([group_specific_in_prev, level_wide_in_curr]).OnlyEnforceIf(undesired_group_to_level_transition)
                # Implications لضمان الربط الصحيح (اختياري مع Minimize لكن يفضل وضعه للوضوح)
                model.AddImplication(undesired_group_to_level_transition, group_specific_in_prev)
                model.AddImplication(undesired_group_to_level_transition, level_wide_in_curr)

                # إضافة العقوبة إلى دالة الهدف
                objective_terms.append(undesired_group_to_level_transition * GROUP_TO_LEVEL_TRANSITION_PENALTY_WEIGHT)


print("  - اكتملت إضافة هدف معاقبة الانتقال المباشر من محاضرة مجموعة إلى محاضرة مستوى.")
# --- (نهاية كود القيد المرن) ---
# --- (الكود التالي يوضع ضمن القيود المرنة في المرحلة 4، مع objective_terms) ---
print("  - إضافة هدف معاقبة تجاور محاضرات المستوى والمجموعات المنفصلة...")

# اختر وزنًا مناسبًا للعقوبة
LEVEL_GROUP_ADJACENCY_PENALTY_WEIGHT = penalty_weights.get("LEVEL_GROUP_ADJACENCY", 1) # مثال لوزن العقوبة

sorted_slot_ids = sorted(slot_ids) # تأكد من أن الفترات مرتبة

for dept_id, level_id in all_dept_level_keys: # استخدم المفاتيح المخزنة
    for day_id in day_ids:
        # المرور على الفترات المتجاورة
        for i in range(len(sorted_slot_ids) - 1):
            slot1_id = sorted_slot_ids[i]
            slot2_id = sorted_slot_ids[i+1]

            # الحصول على متغيرات المؤشر المخزنة
            key1 = (dept_id, level_id, day_id, slot1_id)
            key2 = (dept_id, level_id, day_id, slot2_id)

            # استخدم .get لتجنب الأخطاء إذا لم يتم تعريف المؤشر لسبب ما (نادر)
            level_wide_s1 = single_sched_vars.get(key1)
            group_spec_s1 = multi_sched_vars.get(key1)
            level_wide_s2 = single_sched_vars.get(key2)
            group_spec_s2 = multi_sched_vars.get(key2)

            # تحقق من وجود جميع المتغيرات اللازمة قبل إضافة القيود
            if all([level_wide_s1, group_spec_s1, level_wide_s2, group_spec_s2]):

                # الحالة 1: محاضرة مستوى (s1) تليها محاضرة مجموعة (s2)
                adj_penalty_lg = model.NewBoolVar(f'adj_lg_{dept_id}_{level_id}_{day_id}_{slot1_id}')
                # يكون صحيحًا فقط إذا كانت level_wide_s1 صحيحة و group_spec_s2 صحيحة
                model.AddBoolAnd([level_wide_s1, group_spec_s2]).OnlyEnforceIf(adj_penalty_lg)
                model.AddImplication(adj_penalty_lg, level_wide_s1) # ضروري للربط الصحيح
                model.AddImplication(adj_penalty_lg, group_spec_s2) # ضروري للربط الصحيح
                objective_terms.append(adj_penalty_lg * LEVEL_GROUP_ADJACENCY_PENALTY_WEIGHT)


                # الحالة 2: محاضرة مجموعة (s1) تليها محاضرة مستوى (s2)
                adj_penalty_gl = model.NewBoolVar(f'adj_gl_{dept_id}_{level_id}_{day_id}_{slot1_id}')
                # يكون صحيحًا فقط إذا كانت group_spec_s1 صحيحة و level_wide_s2 صحيحة
                model.AddBoolAnd([group_spec_s1, level_wide_s2]).OnlyEnforceIf(adj_penalty_gl)
                model.AddImplication(adj_penalty_gl, group_spec_s1) # ضروري للربط الصحيح
                model.AddImplication(adj_penalty_gl, level_wide_s2) # ضروري للربط الصحيح
                objective_terms.append(adj_penalty_gl * LEVEL_GROUP_ADJACENCY_PENALTY_WEIGHT)

print("  - اكتملت إضافة هدف معاقبة تجاور محاضرات المستوى والمجموعات.")
# --- (نهاية كود القيد المرن) ---
# هدف 3: تقليل الفواصل الطويلة (بين محاضرتين لنفس المجموعة/المدرس في نفس اليوم)
# يتطلب تتبع الفترات، يمكن تبسيطه أو تنفيذه بدقة
# مثال مبسط: عقوبة إذا كانت هناك محاضرة في الفترة 1 و 3 ولكن لا يوجد في 2
for day_id in day_ids:
    # للمدرسين
    for doctor_id in all_doctor_ids:
        lect_in_slot = {}
        for slot_id in slot_ids:
            lect_in_slot[slot_id] = model.NewBoolVar(f'doc_{doctor_id}_day_{day_id}_slot_{slot_id}_has_lect')
            lectures_in_this_slot = [v for k, v in assignments.items() if k[1] == day_id and k[2] == slot_id and k[4] == doctor_id]
            if lectures_in_this_slot:
                 model.Add(sum(lectures_in_this_slot) >= 1).OnlyEnforceIf(lect_in_slot[slot_id])
                 model.Add(sum(lectures_in_this_slot) == 0).OnlyEnforceIf(lect_in_slot[slot_id].Not())
            else:
                 model.Add(lect_in_slot[slot_id] == 0) # لا يمكن أن تكون هناك محاضرة

        # التحقق من الفجوات (مثال: بين الفترة 1 و 3)
        for i in range(len(slot_ids) - 2):
            slot1 = slot_ids[i]
            slot2 = slot_ids[i+1]
            slot3 = slot_ids[i+2]
            gap_var = model.NewBoolVar(f'gap_doc_{doctor_id}_day_{day_id}_slot_{slot2}')
            model.AddBoolAnd([lect_in_slot[slot1], lect_in_slot[slot3], lect_in_slot[slot2].Not()]).OnlyEnforceIf(gap_var)
            # نضيف عقوبة لكل فجوة
            objective_terms.append(gap_var * penalty_weights["PROF_GAP"])

    # للمستويات (بنفس الطريقة، لكن نجمع حسب المستوى)
    for dept_id, level_id in dept_level_keys:
         lect_in_slot = {}
         for slot_id in slot_ids:
             lect_in_slot[slot_id] = model.NewBoolVar(f'dept_{dept_id}_{level_id}_day_{day_id}_slot_{slot_id}_has_lect')
             lectures_in_this_slot = [v for k, v in assignments.items() if k[1] == day_id and k[2] == slot_id and k[0][0] == dept_id and k[0][1] == level_id ]
             if lectures_in_this_slot:
                 model.Add(sum(lectures_in_this_slot) >= 1).OnlyEnforceIf(lect_in_slot[slot_id])
                 model.Add(sum(lectures_in_this_slot) == 0).OnlyEnforceIf(lect_in_slot[slot_id].Not())
             else:
                 model.Add(lect_in_slot[slot_id] == 0)

         for i in range(len(slot_ids) - 2):
             slot1 = slot_ids[i]
             slot2 = slot_ids[i+1]
             slot3 = slot_ids[i+2]
             gap_var = model.NewBoolVar(f'gap_dept_{dept_id}_{level_id}_day_{day_id}_slot_{slot2}')
             model.AddBoolAnd([lect_in_slot[slot1], lect_in_slot[slot3], lect_in_slot[slot2].Not()]).OnlyEnforceIf(gap_var)
             objective_terms.append(gap_var * penalty_weights["DEPT_GAP"])
# --- (الكود التالي يوضع ضمن القيود المرنة في المرحلة 4، مع objective_terms) ---
print("  - إضافة هدف مكافأة نمط النظري المتبوع بالعملي المتوازي...")

# استخدم وزنًا للمكافأة (سيكون سالبًا أو يُطرح من الهدف)
THEORY_PRACTICAL_REWARD_WEIGHT = penalty_weights.get("THEORY_PRACTICAL_REWARD", -15) # مثال لمقدار المكافأة

sorted_slot_ids = sorted(slot_ids)

for dept_id, level_id in all_dept_level_keys:
    for day_id in day_ids:
        for i in range(len(sorted_slot_ids) - 1):
            slot1_id = sorted_slot_ids[i]
            slot2_id = sorted_slot_ids[i+1]

            key1 = (dept_id, level_id, day_id, slot1_id)
            key2 = (dept_id, level_id, day_id, slot2_id)

            # الحصول على متغيرات المؤشر المخزنة
            level_wide_s1 = single_sched_vars.get(key1) # محاضرة مستوى في الفترة 1
            group_spec_s2 = multi_sched_vars.get(key2) # محاضرة مجموعة في الفترة 2

            # تحقق من وجود المتغيرات
            if all([level_wide_s1, group_spec_s2]):

                # متغير للإشارة إلى حدوث النمط المرغوب
                theory_followed_by_groups = model.NewBoolVar(f'reward_tp_{dept_id}_{level_id}_{day_id}_{slot1_id}')

                # النمط يحدث إذا level_wide_s1 صحيح و group_spec_s2 صحيح
                model.AddBoolAnd([level_wide_s1, group_spec_s2]).OnlyEnforceIf(theory_followed_by_groups)
                model.AddImplication(theory_followed_by_groups, level_wide_s1)
                model.AddImplication(theory_followed_by_groups, group_spec_s2)


                # إضافة المكافأة إلى دالة الهدف (ضرب في وزن سالب أو طرح)
                # بما أننا نعمل بـ Minimize، المكافأة تعني إضافة قيمة سالبة
                objective_terms.append(theory_followed_by_groups * THEORY_PRACTICAL_REWARD_WEIGHT)

print("  - اكتملت إضافة هدف مكافأة نمط النظري المتبوع بالعملي المتوازي.")
# --- (نهاية كود القيد المرن) ---

# هدف 4: تجميع أيام المستوى (مثال: عقوبة إذا تجاوز 3 أيام)
TARGET_MAX_DAYS_PER_LEVEL = 3
for dept_id, level_id in dept_level_keys:
    day_used = []
    for day_id in day_ids:
        day_has_lecture = model.NewBoolVar(f'level_{dept_id}_{level_id}_uses_day_{day_id}')
        lectures_on_this_day = [v for k, v in assignments.items() if k[1] == day_id and k[0][0] == dept_id and k[0][1] == level_id]
        if lectures_on_this_day:
             model.Add(sum(lectures_on_this_day) >= 1).OnlyEnforceIf(day_has_lecture)
             model.Add(sum(lectures_on_this_day) == 0).OnlyEnforceIf(day_has_lecture.Not())
        else:
             model.Add(day_has_lecture == 0)
        day_used.append(day_has_lecture)

    days_count = sum(day_used)
    # عقوبة لكل يوم زيادة عن الهدف
    over_target_days = model.NewIntVar(0, len(day_ids), f'over_target_days_{dept_id}_{level_id}')
    model.Add(days_count - TARGET_MAX_DAYS_PER_LEVEL <= over_target_days)
    # نضيف عقوبة محسوبة (عدد الأيام الزائدة * الوزن)
    objective_terms.append(over_target_days * penalty_weights["LEVEL_SPREAD_DAYS"])

# هدف 5: ثبات القاعات النظرية لنفس المقرر والمجموعة
# يتطلب تتبع القاعة المستخدمة لكل جلسة - أكثر تعقيدًا
# يمكن إضافة عقوبة إذا كانت (جلسة س لنفس المقرر/المجموعة في قاعة أ) و (جلسة ص لنفس المقرر/المجموعة في قاعة ب)
# سنترك هذا الهدف الآن للتبسيط.


# هدف 6: تجنب محاضرة واحدة في اليوم (للمدرس/للقسم)
# (تم تضمين منطقه ضمن الهدف 1 و 2، باستخدام عقوبة under_min مع التحقق من non_zero)
# يمكن جعل العقوبة منفصلة إذا أردنا:
for day_id in day_ids:
    # للمدرسين (باستثناء الصارم)
    for doctor_id in all_doctor_ids:
        if doctor_id not in doctor_is_local_strict:
            lectures_on_day = [v for k, v in assignments.items() if k[1] == day_id and k[4] == doctor_id]
            if not lectures_on_day: continue
            is_single_lecture_day = model.NewBoolVar(f'single_lect_prof_{doctor_id}_{day_id}')
            model.Add(sum(lectures_on_day) == 1).OnlyEnforceIf(is_single_lecture_day)
            model.Add(sum(lectures_on_day) != 1).OnlyEnforceIf(is_single_lecture_day.Not())
            objective_terms.append(is_single_lecture_day * penalty_weights["SINGLE_LECTURE_DAY_PROF"])

    # للمستويات
    for dept_id, level_id in dept_level_keys:
        lectures_on_day = [v for k, v in assignments.items() if k[1] == day_id and k[0][0] == dept_id and k[0][1] == level_id]
        if not lectures_on_day: continue
        is_single_lecture_day = model.NewBoolVar(f'single_lect_dept_{dept_id}_{level_id}_{day_id}')
        model.Add(sum(lectures_on_day) == 1).OnlyEnforceIf(is_single_lecture_day)
        model.Add(sum(lectures_on_day) != 1).OnlyEnforceIf(is_single_lecture_day.Not())
        objective_terms.append(is_single_lecture_day * penalty_weights["SINGLE_LECTURE_DAY_DEPT"])


# --- 4.3: تحديد دالة الهدف النهائية ---
print("  - تحديد دالة الهدف (Minimize)...")
if objective_terms:
    model.Minimize(sum(objective_terms))
else:
    print("تحذير: لم يتم إضافة أي قيود مرنة لدالة الهدف.")

print("المرحلة 4: اكتملت.")
# -----------------------------------------------------------------------------
# المرحلة 5: حل النموذج باستخدام CP-SAT Solver
# -----------------------------------------------------------------------------
print("المرحلة 5: جاري حل النموذج...")
solver = cp_model.CpSolver()

# تحديد وقت أقصى للحل (بالثواني) - مهم للمشاكل الكبيرة
solver.parameters.max_time_in_seconds = 120.0 #120 مثال: دقيقتان
# يمكن تفعيل سجل البحث لرؤية تقدم الحل
# solver.parameters.log_search_progress = True

status = solver.Solve(model)

print("المرحلة 5: اكتملت.")
# -----------------------------------------------------------------------------
# المرحلة 6: معالجة وعرض النتائج
# -----------------------------------------------------------------------------
print("المرحلة 6: جاري معالجة وعرض النتائج...")

if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
    print(f"تم العثور على حل! الحالة: {solver.StatusName(status)}")
    if objective_terms:
         print(f"قيمة دالة الهدف (مجموع العقوبات): {solver.ObjectiveValue()}")

    # --- استخراج الجدول ---
    schedule = []
    assigned_session_keys = set()
    for var_key, var in assignments.items():
        if solver.Value(var):
            session_key, day_id, slot_id, room_id, doctor_id = var_key
            details = session_details[session_key]
            schedule.append({
                "DepartmentID": details['dept'],
                "LevelID": details['level'],
                "CourseID": details['course'],
                "CourseName": details['course_name'],
                "CourseType": details['type'], # 1: Theo, 0: Prac
                "GroupNum": details['group'],
                "Day": Days[day_id],
                "StartTime": TimeSlots[slot_id][0],
                "EndTime": TimeSlots[slot_id][1],
                "RoomID": room_id,
                "RoomName": all_room_data[room_id]['RoomName'],
                "DoctorID": doctor_id,
                "DoctorName": all_doctors_data[doctor_id]['DoctorName']
            })
            assigned_session_keys.add(session_key)

    # --- التحقق من الجلسات التي لم يتم جدولتها (نظريًا لا يجب أن يحدث إذا كان الحل FEASIBLE) ---
    unassigned_sessions = [s for s in all_sessions if s not in assigned_session_keys and s in session_details] # Check if s has details
    if unassigned_sessions:
        print("\nتحذير: الجلسات التالية لم يتم جدولتها:")
        for s in unassigned_sessions:
            print(f"  - {s} ({session_details[s]['course_name']})")

    # --- عرض الجدول (مثال: تجميع حسب القسم والمستوى) ---
    schedule.sort(key=lambda x: (x['DepartmentID'], x['LevelID'], day_ids.index(next(k for k,v in Days.items() if v == x['Day'])), x['StartTime']))

    print("\n--- الجدول الدراسي ---")
    current_dept_level = None
    for entry in schedule:
        dept_level_key = (entry['DepartmentID'], entry['LevelID'])
        if dept_level_key != current_dept_level:
            print(f"\n=== القسم: {entry['DepartmentID']} - المستوى: {entry['LevelID']} ===")
            current_dept_level = dept_level_key
            print(f"{'اليوم':<10} | {'الوقت':<12} | {'المقرر':<25} | {'النوع':<5} | {'مجموعة':<7} | {'القاعة':<10} | {'المدرس':<15}")
            print("-" * 90)

        ctype = "نظري" if entry['CourseType'] == 1 else "عملي"
        print(f"{entry['Day']:<10} | {entry['StartTime'][:5]}-{entry['EndTime'][:5]:<6} | {entry['CourseName']:<25} | {ctype:<5} | {entry['GroupNum']:<7} | {entry['RoomName']:<10} | {entry['DoctorName']:<15}")

    # --- (اختياري) عرض تفاصيل الانتهاكات للقيود المرنة ---
    # يتطلب استرجاع قيم متغيرات الجزاء وفحصها

elif status == cp_model.INFEASIBLE:
    print("الحالة: لا يمكن إيجاد حل يحقق جميع القيود الصلبة.")
    print("  - حاول تخفيف بعض القيود الصلبة أو زيادة وقت الحل.")
    print("  - تحقق من وجود تعارضات منطقية في البيانات (مثل عدم توفر مدرس/قاعة لمقرر إلزامي).")
elif status == cp_model.MODEL_INVALID:
    print("الحالة: النموذج غير صالح. تحقق من تعريف القيود والمتغيرات.")
else:
    print(f"الحالة: {solver.StatusName(status)}. قد يكون الوقت المحدد غير كافٍ.")

print("المرحلة 6: اكتملت.")
# -----------------------------------------------------------------------------