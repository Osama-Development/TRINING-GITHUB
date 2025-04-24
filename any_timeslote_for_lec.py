import collections
from ortools.sat.python import cp_model
import pandas as pd

# --- افتراض أن بيانات المدخلات موجودة كما في الكود الأصلي ---
# doctor_local, doctor_Employ, Departments, Rooms, Transformed_Courses, etc.
# --- Data for: doctor_local ---
# --- Data for: doctor_local ---

print("المرحلة 0: جاري تحميل وإعداد البيانات...")
# (كود تحميل البيانات الأصلي)
Days = {d['id']: d['day_name'] for d in [{'id': 1, 'day_name': 'Saturday'}, {'id': 2, 'day_name': 'Sunday'}, {'id': 3, 'day_name': 'Monday'}, {'id': 4, 'day_name': 'Tuesday'}, {'id': 5, 'day_name': 'Wednesday'}, {'id': 6, 'day_name': 'Thursday'}]}
TimeSlots = {ts['id_slot']: (ts['start_timeslot'], ts['end_timeslot']) for ts in [{'id_slot': 1, 'slot_name': 1, 'start_timeslot': '08:00:00', 'end_timeslot': '10:00:00'}, {'id_slot': 2, 'slot_name': 2, 'start_timeslot': '10:00:00', 'end_timeslot': '12:00:00'}, {'id_slot': 3, 'slot_name': 3, 'start_timeslot': '12:00:00', 'end_timeslot': '14:00:00'}, {'id_slot': 4, 'slot_name': 4, 'start_timeslot': '14:00:00', 'end_timeslot': '16:00:00'}]}
day_ids = list(Days.keys())
# --- تأكد من فرز slot_ids حسب وقت البدء ---
sorted_slot_ids = sorted(TimeSlots.keys(), key=lambda x: TimeSlots[x][0])
slot_id_to_index = {slot_id: index for index, slot_id in enumerate(sorted_slot_ids)}
num_slots_per_day = len(sorted_slot_ids)
GeneralSettings = [ { 'week_start_day_id': 1,'week_end_day_id': 6,'holiday_day_id': 7,
                      'max_lectures_per_day_department': 4,'min_lectures_per_day_department': 2,
                      'max_lectures_per_day_professor': 4,'min_lectures_per_day_professor': 2}]
print("المرحلة 0: اكتملت.")

# -----------------------------------------------------------------------------
# المرحلة 1: تحديد كل جلسات المحاضرات المطلوبة (مع إضافة المدة)
# -----------------------------------------------------------------------------
print("المرحلة 1: جاري تحديد جلسات المحاضرات المطلوبة (مع المدة)...")
all_sessions = []
session_details = {}
course_info = {c['CourseID']: c for c in Transformed_Courses} # الآن يتضمن LectureHours

# --- كود المرحلة 1 الأصلي ---
# ... (نفس الكود لإنشاء all_sessions) ...
# --- تعديل لإضافة duration وتحديد الأولويات ---
high_priority_sessions = [] # جلسات طويلة + مجموعات
medium_priority_sessions = [] # جلسات نظرية + مجموعات

for dept in Departments:
    dept_id = dept['DepartmentID']
    for level in dept['Levels']:
        level_id = level['LevelID']
        student_count_level = level['StudentCount'] # العدد الكلي للمستوى
        # معالجة المقررات النظرية
        for course_data in level['Courses']['Theoretical']:
            course_id = course_data['CourseID']
            groups_count = course_data['GroupsCount']
            c_type = 1 # Theoretical
            linked_practical_id = course_data.get('LinkedPracticalID')
            duration = course_info[course_id].get('LectureHours', 1) # الحصول على المدة

            for group_num in range(1, groups_count + 1):
                session_key = (dept_id, level_id, course_id, c_type, group_num)
                all_sessions.append(session_key)
                session_details[session_key] = {
                    'dept': dept_id, 'level': level_id, 'course': course_id,
                    'type': c_type, 'group': group_num,
                    'student_count': student_count_level, # العدد الكلي للمستوى للنظري
                    'course_name': course_info[course_id]['CourseName'],
                    'linked_practical': linked_practical_id,
                    'duration': duration # تخزين المدة
                }
                # تحديد الأولوية
                if duration > 1 and groups_count > 1:
                    high_priority_sessions.append(session_key)
                elif c_type == 1 and groups_count > 1:
                    medium_priority_sessions.append(session_key)

        # معالجة المقررات العملية
        for course_data in level['Courses']['Practical']:
            course_id = course_data['CourseID']
            groups_count = course_data['GroupsCount']
            c_type = 0 # Practical
            practical_group_size = -(-student_count_level // groups_count) # Ceiling division
            preferred_rooms = [r['RoomID'] for r in course_data['Rooms']]
            duration = course_info[course_id].get('LectureHours', 1) # الحصول على المدة

            for group_num in range(1, groups_count + 1):
                session_key = (dept_id, level_id, course_id, c_type, group_num)
                all_sessions.append(session_key)
                session_details[session_key] = {
                    'dept': dept_id, 'level': level_id, 'course': course_id,
                    'type': c_type, 'group': group_num,
                    'student_count': practical_group_size, # عدد طلاب المجموعة العملية
                    'course_name': course_info[course_id]['CourseName'],
                    'preferred_rooms': preferred_rooms,
                    'duration': duration # تخزين المدة
                }
                 # تحديد الأولوية (عملي طويل + مجموعات)
                if duration > 1 and groups_count > 1:
                    high_priority_sessions.append(session_key)


print(f"المرحلة 1: تم تحديد {len(all_sessions)} جلسة محاضرة.")
print(f"   - جلسات أولوية عليا (طويلة+مجموعات): {len(high_priority_sessions)}")
print(f"   - جلسات أولوية متوسطة (نظري+مجموعات): {len(medium_priority_sessions)}")

# -----------------------------------------------------------------------------
# المرحلة 2: معرفة الموارد (مع تعديل لحساب التوفر المتتالي لاحقاً)
# -----------------------------------------------------------------------------
print("المرحلة 2: جاري معالجة الموارد (المدرسون والقاعات)...")
# --- كود المرحلة 2 الأصلي (لا تغييرات كبيرة هنا) ---
all_doctors_data = {d['DoctorID']: d for d in doctor_local + doctor_Employ}
course_to_doctors = collections.defaultdict(list)
doctor_courses = collections.defaultdict(list)
doctor_availability_map = {}
doctor_required_slots = collections.defaultdict(int)
doctor_is_local_strict = set()

all_doctor_ids = list(all_doctors_data.keys())
for doc_id, doc_data in all_doctors_data.items():
    if 'CourseTaught' in doc_data:
        for taught_info in doc_data['CourseTaught']:
            dept_id = taught_info['DepartmentID']
            if 'Levels' in taught_info:
                 for level_info in taught_info['Levels']:
                    level_id = level_info['LevelID']
                    if 'CoursesID' in level_info:
                        for course_id in level_info['CoursesID']:
                            possible_sessions = [
                                s for s in all_sessions if s[0] == dept_id and s[1] == level_id and s[2] == course_id
                            ]
                            for session_key in possible_sessions:
                                course_to_doctors[session_key].append(doc_id)
                                if session_key not in doctor_courses[doc_id]:
                                     doctor_courses[doc_id].append(session_key)

    availability = doc_data.get('availability')
    if not availability and 'availability_Appointments' in doc_data and doc_data['availability_Appointments']:
        availability = doc_data['availability_Appointments'][0].get('availability')

    if availability:
        total_available_slots = 0
        for day_name, slots in availability.items():
            day_id = next((id for id, name in Days.items() if name == day_name), None)
            if day_id:
                # التأكد من أن طول قائمة التوفر يطابق عدد الفترات
                if len(slots) == num_slots_per_day:
                    for i, is_available in enumerate(slots):
                        slot_id = sorted_slot_ids[i] # استخدام الفترات المرتبة
                        doctor_availability_map[(doc_id, day_id, slot_id)] = bool(is_available)
                        if is_available:
                             total_available_slots += 1
                else:
                    print(f"تحذير: بيانات التوفر للدكتور {doc_id} في يوم {day_name} غير مكتملة ({len(slots)} بدلاً من {num_slots_per_day}).")

    # (منطق doctor_is_local_strict يحتاج لمراجعة ليتناسب مع الكتل لاحقًا)
    if doc_id in [d['DoctorID'] for d in doctor_local]:
         required_lect_count = doc_data.get('Appointments', 0) # هذا عدد المحاضرات وليس الفترات
         # تقدير عدد الفترات المطلوبة (قد لا يكون دقيقاً إذا كان الدكتور يدرس مواد مختلفة المدة)
         # required_slots_estimate = sum(session_details[s]['duration'] for s in doctor_courses[doc_id])
         # doctor_required_slots[doc_id] = required_slots_estimate
         # if total_available_slots > 0 and total_available_slots == required_slots_estimate:
         #      doctor_is_local_strict.add(doc_id)
         #      print(f"  - تنبيه: الدكتور المحلي {doc_data['DoctorName']} ({doc_id}) لديه حالة توفر صارمة (تقديري).")
         pass # تأجيل منطق الصرامة الآن

all_room_data = {r['RoomID']: r for r in Rooms}
room_availability_map = {}
rooms_by_type = {0: [], 1: []}

for room_id, room_data in all_room_data.items():
    rooms_by_type[room_data['Type']].append(room_id)
    availability = room_data.get('Availability')
    if availability:
        for day_name, slots in availability.items():
            day_id = next((id for id, name in Days.items() if name == day_name), None)
            if day_id:
                 if len(slots) == num_slots_per_day:
                    for i, is_available in enumerate(slots):
                        slot_id = sorted_slot_ids[i]
                        room_availability_map[(room_id, day_id, slot_id)] = bool(is_available)
                 else:
                    print(f"تحذير: بيانات التوفر للقاعة {room_id} في يوم {day_name} غير مكتملة ({len(slots)} بدلاً من {num_slots_per_day}).")

all_room_ids = list(all_room_data.keys())
print("المرحلة 2: اكتملت.")


# -----------------------------------------------------------------------------
# المرحلة 3: بناء نموذج CP-SAT وتعريف المتغيرات (بنموذج الكتل)
# -----------------------------------------------------------------------------
print("المرحلة 3: جاري بناء نموذج CP-SAT وتعريف متغيرات الكتل...")
model = cp_model.CpModel()
assignments = {} # قاموس متغيرات القرار: key = (session_key, day_id, start_slot_id, room_id, doctor_id)

# قاموس لحفظ القاعات المستخدمة لكل فترة زمنية لتسهيل فحص التعارض لاحقًا
# Map: (day_id, slot_id) -> list of (assignment_var, resource_keys)
slot_usage = collections.defaultdict(list)

# قاموس لحفظ عدد المجموعات للمقررات (تحتاجه للتحقق من الحالة الخاصة للقاعات)
course_group_count = {}
for dept in Departments:
    dept_id = dept['DepartmentID']
    for level in dept['Levels']:
        level_id = level['LevelID']
        for ctype_key in ['Theoretical', 'Practical']:
            for course_data in level['Courses'][ctype_key]:
                course_id = course_data['CourseID']
                groups_count = course_data['GroupsCount']
                course_group_count[(dept_id, level_id, course_id)] = groups_count

# --- دالة مساعدة للتحقق من التوفر المتتالي ---
def check_consecutive_availability(resource_map, resource_id, day_id, start_slot_index, duration):
    for i in range(duration):
        slot_index = start_slot_index + i
        if slot_index >= len(sorted_slot_ids): return False # خارج اليوم
        slot_id = sorted_slot_ids[slot_index]
        if not resource_map.get((resource_id, day_id, slot_id), False):
            return False # غير متاح في فترة واحدة على الأقل
    return True

total_potential_assignments = 0
for session_key in all_sessions:
    details = session_details[session_key]
    dept_id, level_id, course_id, course_type, group_num = session_key
    duration = details['duration']
    student_count = details['student_count']
    possible_doctors = course_to_doctors.get(session_key, [])
    preferred_practical_rooms = details.get('preferred_rooms', []) # للعملي فقط

    if not possible_doctors: continue

    # تحديد نوع الحالة الخاصة للقاعات (نظري متعدد المجموعات)
    is_special_multi_group_theoretical = False
    if course_type == 1: # نظري
        groups_count = course_group_count.get((dept_id, level_id, course_id), 1)
        if groups_count > 1:
            is_special_multi_group_theoretical = True

    # تحديد القاعات المبدئية حسب النوع
    initial_possible_room_ids = []
    if course_type == 0: # عملي
        initial_possible_room_ids = preferred_practical_rooms # العملي يجب أن يكون في قاعاته المفضلة
    else: # نظري
        initial_possible_room_ids = rooms_by_type.get(1, []) # كل القاعات النظرية مبدئياً

    if not initial_possible_room_ids: continue # لا قاعات من النوع المطلوب

    for day_id in day_ids:
        for start_slot_index, start_slot_id in enumerate(sorted_slot_ids):
            # --- التحقق من أن الكتلة لا تتجاوز نهاية اليوم ---
            if start_slot_index + duration > len(sorted_slot_ids):
                continue # لا يمكن أن تبدأ الكتلة هنا

            # --- تحديد القاعات المسموحة لهذه البداية المحتملة ---
            allowed_room_ids_for_start = []
            if is_special_multi_group_theoretical:
                # حالة خاصة: أصغر قاعتين نظريتين متاحتين لكامل المدة
                available_smallest = []
                potential_special_rooms = []
                for r_id in initial_possible_room_ids: # هي بالفعل نظرية
                     # التحقق من توفر القاعة لكامل المدة
                     if check_consecutive_availability(room_availability_map, r_id, day_id, start_slot_index, duration):
                           potential_special_rooms.append((r_id, all_room_data[r_id]['Capacity']))
                potential_special_rooms.sort(key=lambda x: x[1]) # فرز حسب السعة
                allowed_room_ids_for_start = [r[0] for r in potential_special_rooms[:2]]

            else:
                # حالة عادية: كل القاعات المبدئية المتاحة لكامل المدة
                # (مع التحقق من السعة للنظري العادي)
                for r_id in initial_possible_room_ids:
                    # التحقق من توفر القاعة لكامل المدة
                    if check_consecutive_availability(room_availability_map, r_id, day_id, start_slot_index, duration):
                        # التحقق من السعة فقط للمقررات النظرية العادية
                        if course_type == 1 and not is_special_multi_group_theoretical:
                             if all_room_data[r_id]['Capacity'] >= student_count:
                                allowed_room_ids_for_start.append(r_id)
                        else: # عملي أو نظري خاص (لا تحقق من السعة هنا)
                             allowed_room_ids_for_start.append(r_id)

            # --- المرور على القاعات المسموحة والمدرسين ---
            for room_id in allowed_room_ids_for_start:
                for doctor_id in possible_doctors:
                    # --- التحقق من توفر المدرس لكامل المدة ---
                    if check_consecutive_availability(doctor_availability_map, doctor_id, day_id, start_slot_index, duration):
                        # --- إنشاء المتغير ---
                        var_key = (session_key, day_id, start_slot_id, room_id, doctor_id)
                        var_name = f'assign_{session_key}_{day_id}_{start_slot_id}_{room_id}_{doctor_id}'
                        assignments[var_key] = model.NewBoolVar(var_name)
                        total_potential_assignments += 1

                        # --- تسجيل استخدام الفترات لهذا المتغير المحتمل ---
                        resource_keys = { # الموارد المستخدمة بواسطة هذا التعيين
                            'room': room_id,
                            'doctor': doctor_id,
                            'student_group': (dept_id, level_id, group_num),
                                      'session': session_key }
                        for i in range(duration):
                             slot_index = start_slot_index + i
                             slot_id = sorted_slot_ids[slot_index]
                             slot_usage[(day_id, slot_id)].append((assignments[var_key], resource_keys))


print(f"المرحلة 3: تم تعريف {len(assignments)} متغير قرار محتمل للكتل.")

# -----------------------------------------------------------------------------
# المرحلة 4: إضافة القيود (الصلبة والمرنة) ودالة الهدف (مع تعديلات للكتل)
# -----------------------------------------------------------------------------
print("المرحلة 4: جاري إضافة القيود ودالة الهدف (بنموذج الكتل)...")
objective_terms = []
# --- أوزان العقوبات (قد تحتاج لتعديل) ---
penalty_weights = {
    "PRIORITY_HIGH_NOT_SCHEDULED": 10000,
    "PRIORITY_MEDIUM_NOT_SCHEDULED": 5000,
    "MIN_LECTURES_DEPT": 50,
    "MIN_LECTURES_PROF": 50,
    "MAX_LECTURES_DEPT": 100,
    "MAX_LECTURES_PROF": 100,
    "PROF_GAP": 10, # يحتاج لتعديل
    "DEPT_GAP": 10, # يحتاج لتعديل
    "STUDENT_GROUP_GAP": 15, # يحتاج لتعديل
    "LEVEL_SPREAD_DAYS": 20,
    "ROOM_CHANGE": 5, # قد لا يكون منطقياً مع الكتل
    "SINGLE_LECTURE_DAY_PROF": 30, # يحتاج لتعديل
    "SINGLE_LECTURE_DAY_DEPT": 30, # يحتاج لتعديل
    "LOCAL_STRICT_VIOLATION": 1000
}

# --- 4.1: القيود الصلبة (Hard Constraints) ---
print("  - إضافة القيود الصلبة...")
# --- (الكود التالي يوضع ضمن القيود الصلبة في المرحلة 4) ---
# --- (الكود التالي يوضع ضمن القيود الصلبة في المرحلة 4) ---
print("   - إضافة قيد تطابق عدد المجموعات للمحاضرات المتزامنة...")

# ... (الكود السابق كما هو) ...

for dept_id, level_id in all_dept_level_keys:
    for day_id in day_ids:
        for slot_id in sorted_slot_ids:
            assignments_covering_slot = slot_usage.get((day_id, slot_id), [])
            scheduled_courses_info = []
            # --- *** تعديل هنا: استخدم اسم المتغير أو مؤشره *** ---
            processed_assignments_names = set() # تخزين أسماء المتغيرات المعالجة

            for var, resource_keys in assignments_covering_slot:
                 var_name = var.Name() # الحصول على اسم المتغير
                 # التأكد من معالجة كل متغير مرة واحدة فقط لهذه الفترة باستخدام اسمه
                 if var_name in processed_assignments_names: continue # التحقق بالاسم
                 processed_assignments_names.add(var_name) # إضافة الاسم للمجموعة

                 if 'session' in resource_keys:
                     session_key_found = resource_keys['session']
                     s_dept, s_level, s_course, s_type, s_group = session_key_found
                     if s_dept == dept_id and s_level == level_id:
                         lookup_key = (s_dept, s_level, s_course)
                         groups_count = course_group_count.get(lookup_key, 1)
                         scheduled_courses_info.append({
                             'var': var, # ما زلنا نخزن المتغير نفسه هنا للإضافة للقيد لاحقًا
                             'course_id': s_course,
                             'groups_count': groups_count
                         })

            if len(scheduled_courses_info) <= 1:
                continue

            for i in range(len(scheduled_courses_info)):
                for j in range(i + 1, len(scheduled_courses_info)):
                    info1 = scheduled_courses_info[i]
                    info2 = scheduled_courses_info[j]

                    var1 = info1['var']
                    var2 = info2['var']
                    groups_count1 = info1['groups_count']
                    groups_count2 = info2['groups_count']

                    if groups_count1 != groups_count2:
                        # القيد كما هو: لا يمكن جدولة var1 و var2 معًا
                        model.Add(var1 + var2 <= 1).WithName(f'group_count_match_{dept_id}_{level_id}_{day_id}_{slot_id}_{i}_{j}')

print("   - اكتملت إضافة قيد تطابق عدد المجموعات للمحاضرات المتزامنة.")
# --- (نهاية كود القيد) ---
# القيد 1: كل جلسة يجب أن تُجدول (تبدأ) مرة واحدة بالضبط
sessions_processed_hc1 = set()
for var_key in assignments.keys():
     session_key = var_key[0]
     if session_key not in sessions_processed_hc1:
          possible_starts_for_session = [v for k, v in assignments.items() if k[0] == session_key]
          if possible_starts_for_session:
               model.Add(sum(possible_starts_for_session) == 1)
               sessions_processed_hc1.add(session_key)
          else:
               # إذا لم تكن هناك بدايات ممكنة، فهذا يعني أن الجلسة لا يمكن جدولتها
               # يمكن إضافة متغير عقوبة هنا إذا أردنا السماح بعدم الجدولة كخيار أخير
               print(f"تحذير شديد: لا يمكن إيجاد أي بداية ممكنة للجلسة {session_key} ({session_details[session_key]['course_name']}) ضمن القيود الأولية.")
               # يمكن إضافة متغير بولياني يمثل عدم الجدولة ومعاقبته بشدة
               not_scheduled_var = model.NewBoolVar(f'not_scheduled_{session_key}')
               objective_terms.append(not_scheduled_var * penalty_weights["PRIORITY_HIGH_NOT_SCHEDULED"]*10) # عقوبة هائلة


# القيد 2: منع التعارضات (لا يمكن لموردين استخدام نفس الفترة)
print("   - إضافة قيد منع التعارضات للموارد والفترات...")
processed_resource_slots = set() # لتتبع (نوع_المورد, معرف_المورد, يوم, فترة)

for day_id in day_ids:
    for slot_id in sorted_slot_ids:
        # الحصول على كل متغيرات الجدولة التي تغطي هذه الفترة الزمنية
        assignments_covering_slot = slot_usage.get((day_id, slot_id), [])

        if assignments_covering_slot:
            # تنظيم المتغيرات حسب المورد المستخدم
            vars_by_room = collections.defaultdict(list)
            vars_by_doctor = collections.defaultdict(list)
            vars_by_student_group = collections.defaultdict(list)

            for var, resource_keys in assignments_covering_slot:
                 vars_by_room[resource_keys['room']].append(var)
                 vars_by_doctor[resource_keys['doctor']].append(var)
                 vars_by_student_group[resource_keys['student_group']].append(var)

            # إضافة قيد التعارض لكل مورد في هذه الفترة
            # للقاعات
            for room_id, vars_list in vars_by_room.items():
                if len(vars_list) > 1: # فقط إذا كان هناك احتمال تعارض
                    key = ('room', room_id, day_id, slot_id)
                    if key not in processed_resource_slots:
                        model.Add(sum(vars_list) <= 1).WithName(f'conflict_room_{room_id}_{day_id}_{slot_id}')
                        processed_resource_slots.add(key)
            # للمدرسين
            for doctor_id, vars_list in vars_by_doctor.items():
                 if len(vars_list) > 1:
                    key = ('doctor', doctor_id, day_id, slot_id)
                    if key not in processed_resource_slots:
                        model.Add(sum(vars_list) <= 1).WithName(f'conflict_doctor_{doctor_id}_{day_id}_{slot_id}')
                        processed_resource_slots.add(key)
            # لمجموعات الطلاب
            for student_group_key, vars_list in vars_by_student_group.items():
                 if len(vars_list) > 1:
                    key = ('student_group', student_group_key, day_id, slot_id)
                    if key not in processed_resource_slots:
                         model.Add(sum(vars_list) <= 1).WithName(f'conflict_student_{student_group_key}_{day_id}_{slot_id}')
                         processed_resource_slots.add(key)

# --- (الكود التالي يوضع ضمن القيود الصلبة في المرحلة 4) ---
print("   - إضافة قيد منع التزامن بين محاضرات المستوى والمجموعات الفرعية...")

# نحتاج إلى session_details و course_group_count
# تأكد من أنهما متاحان في هذا النطاق

# تحديد مفاتيح القسم والمستوى الفريدة
all_dept_level_keys = set((s[0], s[1]) for s in all_sessions)

for dept_id, level_id in all_dept_level_keys:
    for day_id in day_ids:
        for slot_id in sorted_slot_ids:
            # الحصول على كل متغيرات الجدولة التي تغطي هذه الفترة الزمنية لهذا القسم والمستوى
            assignments_covering_slot = slot_usage.get((day_id, slot_id), [])

            level_wide_vars_in_slot = []
            group_specific_vars_in_slot = []

            # تصنيف المتغيرات التي تخص هذا القسم والمستوى
            for var, resource_keys in assignments_covering_slot:
                # استخراج session_key من اسم المتغير أو مفتاح var_key الأصلي
                # (نفترض أن var.Name() يحتوي على معلومات كافية أو أننا بحاجة للبحث في assignments)
                # الطريقة الأسهل: البحث في assignments الأصلي
                session_key_found = None
                for k, v in assignments.items():
                     # قد يكون هناك تطابق في قيم المتغيرات، الأفضل البحث بالمفتاح
                     # سنحتاج إلى طريقة للربط بين var وقيمته في assignments
                     # الطريقة الأكثر أمانًا: إعادة البحث عن الجلسة من var.Name() إذا كان الاسم منظمًا
                     # أو الأفضل تعديل slot_usage لتخزين session_key
                     # --- تعديل مقترح لـ slot_usage في المرحلة 3 ---
                     # resource_keys = { ... 'session': session_key }
                     # slot_usage[(day_id, slot_id)].append((var, resource_keys))
                     # --- نهاية التعديل المقترح ---

                     # --- باستخدام التعديل المقترح ---
                     if 'session' in resource_keys and v == var: # التأكد من أن var هو نفسه
                         session_key_found = resource_keys['session']
                         break # وجدنا المطابقة

                if session_key_found:
                     s_dept, s_level, s_course, s_type, s_group = session_key_found
                     # التأكد من أن الجلسة تخص هذا القسم والمستوى
                     if s_dept == dept_id and s_level == level_id:
                         lookup_key = (s_dept, s_level, s_course)
                         groups_count = course_group_count.get(lookup_key, 1)

                         if s_type == 1 and groups_count == 1: # نظري ومجموعة واحدة -> Level-Wide
                             level_wide_vars_in_slot.append(var)
                         else: # عملي أو نظري متعدد المجموعات -> Group-Specific
                             group_specific_vars_in_slot.append(var)
                # else:
                     # Handle cases where var couldn't be mapped back if session wasn't stored
                     # print(f"Warning: Could not map var {var.Name()} back to session key.")


            # --- إضافة القيد الأساسي ---
            # متغير مساعد: هل هناك محاضرة مستوى مجدولة؟
            is_level_wide_scheduled = model.NewBoolVar(f'level_sched_{dept_id}_{level_id}_{day_id}_{slot_id}')
            if level_wide_vars_in_slot:
                model.Add(sum(level_wide_vars_in_slot) >= 1).OnlyEnforceIf(is_level_wide_scheduled)
                model.Add(sum(level_wide_vars_in_slot) == 0).OnlyEnforceIf(is_level_wide_scheduled.Not())
            else:
                model.Add(is_level_wide_scheduled == 0) # لا يمكن جدولته إذا لم تكن هناك متغيرات له

            # متغير مساعد: هل هناك محاضرة مجموعة فرعية مجدولة؟
            is_group_specific_scheduled = model.NewBoolVar(f'group_sched_{dept_id}_{level_id}_{day_id}_{slot_id}')
            if group_specific_vars_in_slot:
                 # نستخدم >= 1 لأن أكثر من مجموعة فرعية قد تكون مجدولة بالتوازي
                model.Add(sum(group_specific_vars_in_slot) >= 1).OnlyEnforceIf(is_group_specific_scheduled)
                model.Add(sum(group_specific_vars_in_slot) == 0).OnlyEnforceIf(is_group_specific_scheduled.Not())
            else:
                model.Add(is_group_specific_scheduled == 0)

            # القيد: لا يمكن أن يكون كلا النوعين مجدولاً في نفس الوقت لهذا القسم/المستوى
            model.Add(is_level_wide_scheduled + is_group_specific_scheduled <= 1).WithName(f'no_mix_{dept_id}_{level_id}_{day_id}_{slot_id}')


print("   - اكتملت إضافة قيد منع التزامن بين محاضرات المستوى والمجموعات الفرعية.")

# --- (نهاية كود القيد) ---

# --- *** تعديل مطلوب في المرحلة 3 لتخزين session_key في slot_usage *** ---
# داخل حلقة إنشاء المتغيرات في المرحلة 3، عدّل تسجيل slot_usage كالتالي:

# --- (داخل الحلقة في المرحلة 3، بعد إنشاء assignments[var_key]) ---
# resource_keys = { # الموارد المستخدمة بواسطة هذا التعيين
#     'room': room_id,
#     'doctor': doctor_id,
#     'student_group': (dept_id, level_id, group_num), # مفتاح مجموعة الطلاب
#     'session': session_key  # <--- *** الإضافة المطلوبة هنا ***
# }
# for i in range(duration):
#      slot_index = start_slot_index + i
#      slot_id = sorted_slot_ids[slot_index]
#      slot_usage[(day_id, slot_id)].append((assignments[var_key], resource_keys))
# --- (نهاية التعديل في المرحلة 3) ---
# (قيود أخرى مثل منع تعارض نظري مجموعة واحدة مع عملي مجموعات تحتاج إعادة تصميم كامل)
# (قيود المحلي الصارم تحتاج إعادة تصميم كامل لحساب الفترات المستخدمة بالكتل)

# --- 4.2: القيود المرنة (Soft Constraints) ---
print("  - إضافة القيود المرنة (كدالة هدف)...")

# هدف الأولوية: معاقبة عدم جدولة الجلسات ذات الأولوية
print("   - إضافة عقوبات عدم جدولة الجلسات ذات الأولوية...")
scheduled_priority_vars = {} # لتخزين متغيرات التأكيد

# الأولوية العليا
for session_key in high_priority_sessions:
     possible_starts = [v for k, v in assignments.items() if k[0] == session_key]
     if possible_starts: # فقط إذا كان يمكن جدولتها نظرياً
         is_scheduled = model.NewBoolVar(f'sched_hp_{session_key}')
         model.Add(sum(possible_starts) == is_scheduled)
         objective_terms.append((1 - is_scheduled) * penalty_weights["PRIORITY_HIGH_NOT_SCHEDULED"])
         scheduled_priority_vars[session_key] = is_scheduled
     else:
          # تمت معاقبتها بالفعل في القيد الصلب 1 كتحذير شديد
          pass

# الأولوية المتوسطة
for session_key in medium_priority_sessions:
    # تأكد أنها ليست أيضاً أولوية عليا
    if session_key not in high_priority_sessions:
         possible_starts = [v for k, v in assignments.items() if k[0] == session_key]
         if possible_starts:
             is_scheduled = model.NewBoolVar(f'sched_mp_{session_key}')
             model.Add(sum(possible_starts) == is_scheduled)
             objective_terms.append((1 - is_scheduled) * penalty_weights["PRIORITY_MEDIUM_NOT_SCHEDULED"])
             scheduled_priority_vars[session_key] = is_scheduled
         else:
              # معاقبة عدم إمكانية الجدولة
               objective_terms.append(1 * penalty_weights["PRIORITY_MEDIUM_NOT_SCHEDULED"] * 10) # عقوبة هائلة لعدم إمكانية الجدولة


# (باقي القيود المرنة مثل الفجوات، توازن المحاضرات، إلخ، تحتاج إعادة تصميم مع نموذج الكتل)
# على سبيل المثال، لحساب الفجوات الطلابية:
# 1. لكل مجموعة طلابية ويوم:
# 2. حدد الفترات التي تغطيها المحاضرات المجدولة لهذه المجموعة.
# 3. ابحث عن فترات فارغة بين فترات مشغولة.

# --- مثال مبسط جداً لعقوبة الفجوات الطلابية (يحتاج تحسين) ---
print("   - إضافة عقوبات الفجوات الطلابية (مبسط)...")
student_group_keys = set(val['student_group'] for day_slot_list in slot_usage.values() for var, val in day_slot_list)

for group_key in student_group_keys:
     dept_id, level_id, group_identifier = group_key
     group_str = f"{dept_id}_{level_id}_{group_identifier}"

     for day_id in day_ids:
         # متغيرات تشير إلى ما إذا كانت الفترة مشغولة *لهذه المجموعة*
         slot_busy_for_group = {}
         possible_lectures_exist_on_day = False

         for slot_index, slot_id in enumerate(sorted_slot_ids):
             busy_var = model.NewBoolVar(f'sgrp_busy_{group_str}_{day_id}_{slot_id}')
             slot_busy_for_group[slot_id] = busy_var

             # ابحث عن أي متغير يبدأ أو يغطي هذه الفترة لهذه المجموعة
             assignments_covering_slot_for_group = []
             if (day_id, slot_id) in slot_usage:
                  for var, resource_keys in slot_usage[(day_id, slot_id)]:
                      if resource_keys['student_group'] == group_key:
                          assignments_covering_slot_for_group.append(var)

             if assignments_covering_slot_for_group:
                  possible_lectures_exist_on_day = True
                  model.Add(sum(assignments_covering_slot_for_group) >= 1).OnlyEnforceIf(busy_var)
                  model.Add(sum(assignments_covering_slot_for_group) == 0).OnlyEnforceIf(busy_var.Not())
             else:
                  model.Add(busy_var == 0)

         if not possible_lectures_exist_on_day: continue

         # البحث عن نمط (مشغول، فارغ، مشغول)
         for i in range(len(sorted_slot_ids) - 2):
             s1 = sorted_slot_ids[i]
             s2 = sorted_slot_ids[i+1]
             s3 = sorted_slot_ids[i+2]

             gap_detected = model.NewBoolVar(f'gap_sgrp_{group_str}_day_{day_id}_slot_{s2}')
             model.AddBoolAnd([
                 slot_busy_for_group[s1],
                 slot_busy_for_group[s2].Not(),
                 slot_busy_for_group[s3]
             ]).OnlyEnforceIf(gap_detected)
             objective_terms.append(gap_detected * penalty_weights["STUDENT_GROUP_GAP"])


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
solver.parameters.max_time_in_seconds = 300.0 # زيادة الوقت للنموذج الأكثر تعقيدًا
# solver.parameters.log_search_progress = True
status = solver.Solve(model)
print("المرحلة 5: اكتملت.")

# -----------------------------------------------------------------------------
# المرحلة 6: معالجة وعرض النتائج (مع تعديل لتوسيع الكتل)
# -----------------------------------------------------------------------------
print("المرحلة 6: جاري معالجة وعرض النتائج (بنموذج الكتل)...")

if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
    print(f"تم العثور على حل! الحالة: {solver.StatusName(status)}")
    if objective_terms:
         print(f"قيمة دالة الهدف (مجموع العقوبات): {solver.ObjectiveValue()}")

    schedule = []
    assigned_session_keys_starts = set() # لتتبع الجلسات التي تم العثور على بداية لها

    for var_key, var in assignments.items():
        if solver.Value(var):
            session_key, day_id, start_slot_id, room_id, doctor_id = var_key
            details = session_details[session_key]
            duration = details['duration']
            start_slot_index = slot_id_to_index[start_slot_id]
            assigned_session_keys_starts.add(session_key) # تم جدولة هذه الجلسة

            # --- إنشاء سجلات لكل فترة ضمن الكتلة ---
            for i in range(duration):
                current_slot_index = start_slot_index + i
                if current_slot_index < len(sorted_slot_ids): # تأكد من عدم تجاوز اليوم
                    current_slot_id = sorted_slot_ids[current_slot_index]
                    start_time, end_time = TimeSlots[current_slot_id]
                    schedule.append({
                        "DepartmentID": details['dept'],
                        "LevelID": details['level'],
                        "CourseID": details['course'],
                        "CourseName": details['course_name'],
                        "CourseType": details['type'],
                        "GroupNum": details['group'],
                        "Day": Days[day_id],
                        "StartTime": start_time,
                        "EndTime": end_time,
                        "RoomID": room_id,
                        "RoomName": all_room_data[room_id]['RoomName'],
                        "DoctorID": doctor_id,
                        "DoctorName": all_doctors_data[doctor_id]['DoctorName'],
                        # معلومات إضافية للتحقق (اختياري)
                        "BlockStartSlot": start_slot_id,
                        "Duration": duration
                    })
                else:
                     print(f"تحذير: تجاوزت الكتلة {session_key} نهاية اليوم {day_id}")


    # --- التحقق من الجلسات التي لم يتم جدولتها ---
    unassigned_sessions = [s for s in all_sessions if s not in assigned_session_keys_starts]
    if unassigned_sessions:
        print("\nتحذير: الجلسات التالية لم يتم جدولتها (لم يتم العثور على بداية ممكنة):")
        for s in unassigned_sessions:
            prio = "عليا" if s in high_priority_sessions else ("متوسطة" if s in medium_priority_sessions else "عادية")
            print(f"  - {s} ({session_details[s]['course_name']}) - أولوية: {prio}")

    # --- عرض الجدول (نفس كود العرض السابق، مع تعديل محتمل للحقول الإضافية) ---
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
        # التأكد من عرض الوقت بشكل صحيح
        start_hms = entry['StartTime']
        end_hms = entry['EndTime']
        time_display = f"{start_hms[:5]}-{end_hms[:5]}"

        print(f"{entry['Day']:<10} | {time_display:<12} | {entry['CourseName']:<25} | {ctype:<5} | {entry['GroupNum']:<7} | {entry['RoomName']:<10} | {entry['DoctorName']:<15}")


elif status == cp_model.INFEASIBLE:
    print("الحالة: لا يمكن إيجاد حل يحقق جميع القيود الصلبة.")
    print("  - قد يكون السبب تعارضات متأصلة في البيانات أو صعوبة جدولة الكتل الطويلة.")
    print("  - حاول زيادة وقت الحل، أو تخفيف بعض القيود (خاصة المرنة المتعلقة بالفجوات إذا كانت معقدة).")
    print("  - تحقق من التحذيرات الشديدة حول عدم إمكانية جدولة بعض الجلسات.")

    # --- (اختياري) تحليل سبب عدم الحل باستخدام AnalyzeInfeasibleProblem() ---
    # print(solver.SufficientAssumptionsForInfeasibility())

elif status == cp_model.MODEL_INVALID:
    print("الحالة: النموذج غير صالح. تحقق من تعريف القيود والمتغيرات.")
else:
    print(f"الحالة: {solver.StatusName(status)}. قد يكون الوقت المحدد غير كافٍ.")

print("المرحلة 6: اكتملت.")