# =============================================================================
# الخلية الثانية: كود إعادة توزيع القاعات النظرية (نسخة مصححة)
# (قم بتشغيل هذه الخلية بعد الخلية الأولى)
# =============================================================================
import collections
import copy # للتأكد من أننا لا نعدل القائمة الأصلية إذا لم نرغب في ذلك
import math # لاستخدام التقريب للأعلى (ceil)

print("\nالمرحلة 7: جاري إعادة توزيع القاعات النظرية بناءً على السعة (بالمنطق الصحيح)...")

# --- التحقق من وجود المتغيرات المطلوبة ---
required_vars = ['schedule', 'Rooms', 'Departments', 'Days', 'TimeSlots_list']
missing_vars = [var for var in required_vars if var not in locals() and var not in globals()]

if missing_vars:
    print(f"خطأ: المتغيرات التالية غير موجودة: {', '.join(missing_vars)}")
    print("يرجى التأكد من تشغيل الخلية الأولى بنجاح وأن البيانات الأساسية (Rooms, Departments, Days, TimeSlots_list) معرفة.")
    # يمكنك إيقاف التنفيذ هنا إذا أردت
    # raise NameError(f"Required variables missing: {', '.join(missing_vars)}")
else:
    print("   - تم العثور على بيانات الجدول والقاعات والأقسام...")

    # --- 7.1: إعداد البيانات المساعدة ---
    print("   - تجهيز البيانات المساعدة لإعادة التوزيع...")

    # قاموس لعدد الطلاب لكل مستوى
    level_student_count = {}
    for dept in Departments:
        for level in dept['Levels']:
            level_student_count[(dept['DepartmentID'], level['LevelID'])] = level['StudentCount']

    # قاموس لعدد المجموعات للمقررات النظرية فقط
    theoretical_group_count = {}
    for dept in Departments:
        dept_id = dept['DepartmentID']
        for level in dept['Levels']:
            level_id = level['LevelID']
            if 'Theoretical' in level['Courses']:
                for course_data in level['Courses']['Theoretical']:
                    theoretical_group_count[(dept_id, level_id, course_data['CourseID'])] = course_data['GroupsCount']

    # قائمة القاعات النظرية مرتبة تصاعدياً حسب السعة
    theoretical_rooms_sorted = sorted([r for r in Rooms if r['Type'] == 1], key=lambda x: x['Capacity'])
    if not theoretical_rooms_sorted:
        print("تحذير: لا توجد قاعات نظرية (Type=1) معرفة في بيانات 'Rooms'. لا يمكن إعادة التوزيع.")
    else:
         print(f"   - تم العثور على {len(theoretical_rooms_sorted)} قاعة نظرية.")

    # إنشاء قاموس لسهولة الوصول لبيانات القاعات
    room_details_lookup = {r['RoomID']: r for r in Rooms}

    # إنشاء قاموس لتوفر القاعات
    room_availability_map_reassign = {}
    day_name_to_id = {name: id for id, name in Days.items()}
    timeslot_lookup_reassign = {ts['start_timeslot']: ts['id_slot'] for ts in TimeSlots_list}

    for room in Rooms:
        room_id = room['RoomID']
        if room.get('Availability'):
            for day_name, slots_availability in room['Availability'].items():
                day_id = day_name_to_id.get(day_name)
                if day_id:
                    # نفترض أن الفترات مرتبة 1, 2, 3, 4 وأن slot_ids هي [1, 2, 3, 4]
                    slot_ids_ordered = sorted(timeslot_lookup_reassign.values())
                    if len(slots_availability) == len(slot_ids_ordered):
                         for i, is_available in enumerate(slots_availability):
                            slot_id = slot_ids_ordered[i]
                            room_availability_map_reassign[(room_id, day_id, slot_id)] = bool(is_available)
                    else:
                         print(f"تحذير: عدم تطابق عدد فترات التوفر للقاعة {room_id} في يوم {day_name}.")


    # --- 7.2: تحديد المحاضرات النظرية وحساب السعة المطلوبة ---
    print("   - تحديد المحاضرات النظرية وحساب السعة المطلوبة لكل مجموعة...")
    theoretical_lectures_to_reassign = []
    schedule_copy = copy.deepcopy(schedule) # نعمل على نسخة

    for index, entry in enumerate(schedule_copy):
        if entry['CourseType'] == 1: # 1 = نظري
            dept_id = entry['DepartmentID']
            level_id = entry['LevelID']
            course_id = entry['CourseID']
            day_name = entry['Day']
            start_time = entry['StartTime']

            day_id = day_name_to_id.get(day_name)
            slot_id = timeslot_lookup_reassign.get(start_time)
            total_level_students = level_student_count.get((dept_id, level_id), 0)
            total_groups_for_course = theoretical_group_count.get((dept_id, level_id, course_id), 1)

            # --- *** حساب السعة المطلوبة الصحيح *** ---
            required_capacity = 0
            if total_level_students <= 0:
                print(f"تحذير: عدد طلاب المستوى ({dept_id}, {level_id}) هو صفر أو غير موجود. تجاهل المحاضرة: {entry}")
                continue
            if total_groups_for_course <= 0:
                 print(f"تحذير: عدد مجموعات المقرر النظري {course_id} هو صفر أو غير صالح. تجاهل المحاضرة: {entry}")
                 continue

            if total_groups_for_course == 1:
                # المقرر للمستوى كله، نحتاج سعة المستوى
                required_capacity = total_level_students
            else:
                # المقرر مقسم، نقسم عدد الطلاب على عدد المجموعات ونقرب للأعلى
                required_capacity = math.ceil(total_level_students / total_groups_for_course)
                # required_capacity = -(-total_level_students // total_groups_for_course) # طريقة أخرى للتقريب للأعلى للأعداد الصحيحة

            if day_id is None or slot_id is None:
                 print(f"تحذير: لم يتم العثور على Day ID أو Slot ID للمحاضرة: {entry}. سيتم تجاهلها.")
                 continue

            theoretical_lectures_to_reassign.append({
                'original_index': index,
                'dept_id': dept_id,
                'level_id': level_id,
                'course_id': course_id,
                'group_num': entry['GroupNum'],
                'course_name': entry['CourseName'],
                'day_id': day_id,
                'slot_id': slot_id,
                'total_groups': total_groups_for_course,
                'required_capacity': required_capacity, # السعة المحسوبة للمجموعة الواحدة
                'assigned_room_id': None
            })
            # إزالة القاعة القديمة من النسخة
            entry['RoomID'] = None
            entry['RoomName'] = '؟؟؟ سيتم التحديد ؟؟؟'

    print(f"   - تم تحديد {len(theoretical_lectures_to_reassign)} محاضرة نظرية مع حساب السعة المطلوبة لكل مجموعة.")

    # --- 7.3: تجميع المحاضرات حسب الوقت للتعامل مع التزامن ---
    lectures_by_time = collections.defaultdict(list)
    for lecture_info in theoretical_lectures_to_reassign:
        time_key = (lecture_info['day_id'], lecture_info['slot_id'])
        lectures_by_time[time_key].append(lecture_info)

    # --- 7.4: عملية إعادة التوزيع (بالمنطق المصحح) ---
    print("   - بدء عملية إعادة التوزيع (إعطاء الأولوية للمقررات متعددة المجموعات)...")
    assigned_rooms_in_slot = set() # لتتبع القاعات المستخدمة: (room_id, day_id, slot_id)
    successfully_assigned_count = 0
    failed_assignment_lectures = []

    sorted_time_keys = sorted(lectures_by_time.keys())

    for day_id, slot_id in sorted_time_keys:
        lectures_in_this_slot = lectures_by_time[(day_id, slot_id)]
        # فرز داخل الفترة: أولاً حسب عدد المجموعات الكلي (تنازلي)، ثم حسب المقرر والمجموعة
        lectures_in_this_slot.sort(key=lambda x: (-x['total_groups'], x['course_id'], x['group_num']))

        # تجميع المتزامنة لنفس المقرر متعدد المجموعات
        multi_group_concurrent = collections.defaultdict(list)
        single_group_lectures = []

        for lecture in lectures_in_this_slot:
            if lecture['total_groups'] > 1:
                 course_key = (lecture['dept_id'], lecture['level_id'], lecture['course_id'])
                 multi_group_concurrent[course_key].append(lecture)
            else:
                 single_group_lectures.append(lecture)

        # 1. معالجة المقررات المتعددة المجموعات أولاً
        for course_key, concurrent_lectures in multi_group_concurrent.items():
            num_needed = len(concurrent_lectures)
            # السعة المطلوبة لكل مجموعة من المجموعات المتزامنة (تم حسابها مسبقاً)
            required_capacity_per_group = concurrent_lectures[0]['required_capacity']
            found_rooms_for_course = []

            # البحث عن أصغر قاعات متاحة وكافية (بالسعة المطلوبة للمجموعة)
            possible_rooms = []
            for room in theoretical_rooms_sorted:
                room_id = room['RoomID']
                room_key_in_slot = (room_id, day_id, slot_id)

                # هل القاعة مناسبة (السعة المطلوبة للمجموعة) ومتاحة؟
                if room['Capacity'] >= required_capacity_per_group and \
                   room_availability_map_reassign.get(room_key_in_slot, False) and \
                   room_key_in_slot not in assigned_rooms_in_slot:
                    possible_rooms.append(room)

            # هل وجدنا قاعات كافية؟
            if len(possible_rooms) >= num_needed:
                 # اختر أصغر 'num_needed' قاعة من القاعات الممكنة
                 found_rooms_for_course = possible_rooms[:num_needed]
                 for i in range(num_needed):
                     lecture_to_assign = concurrent_lectures[i]
                     chosen_room = found_rooms_for_course[i]
                     chosen_room_id = chosen_room['RoomID']
                     chosen_room_key_in_slot = (chosen_room_id, day_id, slot_id)

                     lecture_to_assign['assigned_room_id'] = chosen_room_id
                     assigned_rooms_in_slot.add(chosen_room_key_in_slot)
                     successfully_assigned_count += 1
                     # تحديث الجدول الأصلي في النسخة
                     original_schedule_entry = schedule_copy[lecture_to_assign['original_index']]
                     original_schedule_entry['RoomID'] = chosen_room_id
                     original_schedule_entry['RoomName'] = chosen_room['RoomName']
            else:
                 print(f"  - تحذير: لم يتم العثور على {num_needed} قاعات متزامنة مناسبة (سعة >= {required_capacity_per_group}) للمقرر {course_key} في يوم {day_id} الفترة {slot_id}.")
                 for lec in concurrent_lectures:
                     failed_assignment_lectures.append(lec)

        # 2. معالجة المقررات ذات المجموعة الواحدة
        for lecture in single_group_lectures:
             # السعة المطلوبة = العدد الكلي لطلاب المستوى (تم حسابها مسبقاً)
            required_capacity_level = lecture['required_capacity']
            found_room = None
            # ابحث عن أصغر قاعة متاحة وكافية (لسعة المستوى)
            for room in theoretical_rooms_sorted:
                room_id = room['RoomID']
                room_key_in_slot = (room_id, day_id, slot_id)

                if room['Capacity'] >= required_capacity_level and \
                   room_availability_map_reassign.get(room_key_in_slot, False) and \
                   room_key_in_slot not in assigned_rooms_in_slot:
                    found_room = room
                    break

            if found_room:
                 found_room_id = found_room['RoomID']
                 found_room_key_in_slot = (found_room_id, day_id, slot_id)
                 lecture['assigned_room_id'] = found_room_id
                 assigned_rooms_in_slot.add(found_room_key_in_slot)
                 successfully_assigned_count += 1
                 original_schedule_entry = schedule_copy[lecture['original_index']]
                 original_schedule_entry['RoomID'] = found_room_id
                 original_schedule_entry['RoomName'] = found_room['RoomName']
            else:
                 print(f"  - تحذير: لم يتم العثور على قاعة مناسبة (سعة >= {required_capacity_level}) للمحاضرة الفردية: {lecture['course_name']} (مستوى {lecture['level_id']}) في يوم {day_id} الفترة {slot_id}.")
                 failed_assignment_lectures.append(lecture)

    print(f"   - اكتملت محاولة إعادة التوزيع. تم تعيين قاعات لـ {successfully_assigned_count} محاضرة نظرية.")

    # --- 7.5: عرض النتائج والتحذيرات ---
    if failed_assignment_lectures:
        print("\n--- تحذير: فشل تعيين قاعات للمحاضرات النظرية التالية ---")
        failed_assignment_lectures.sort(key=lambda x: (x['day_id'], x['slot_id'], x['course_id']))
        for failed_lec in failed_assignment_lectures:
            print(f"  - المقرر: {failed_lec['course_name']} (قسم {failed_lec['dept_id']}, مستوى {failed_lec['level_id']}, مجموعة {failed_lec['group_num']})")
            print(f"    الوقت: يوم {failed_lec['day_id']} فترة {failed_lec['slot_id']}")
            print(f"    السعة المطلوبة للمجموعة: {failed_lec['required_capacity']}, المجموعات الكلية للمقرر: {failed_lec['total_groups']}")
            print("-" * 20)

    print("\n--- الجدول الدراسي بعد إعادة توزيع القاعات النظرية (بالمنطق الصحيح) ---")
    schedule_copy.sort(key=lambda x: (
        x['DepartmentID'],
        x['LevelID'],
        list(Days.values()).index(x['Day']) if x['Day'] in Days.values() else -1,
        x['StartTime']
    ))

    current_dept_level = None
    for entry in schedule_copy:
        dept_level_key = (entry['DepartmentID'], entry['LevelID'])
        if dept_level_key != current_dept_level:
            dept_name = next((d['DepartmentName'] for d in Departments if d['DepartmentID'] == entry['DepartmentID']), f"قسم {entry['DepartmentID']}")
            level_name = "غير معروف"
            for d in Departments:
                if d['DepartmentID'] == entry['DepartmentID']:
                     found_level = next((l['LevelName'] for l in d['Levels'] if l['LevelID'] == entry['LevelID']), None)
                     if found_level:
                         level_name = found_level
                         break
            print(f"\n=== القسم: {dept_name} - المستوى: {level_name} ===")
            current_dept_level = dept_level_key
            print(f"{'اليوم':<10} | {'الوقت':<12} | {'المقرر':<25} | {'النوع':<5} | {'مجموعة':<7} | {'القاعة':<18} | {'المدرس':<15}")
            print("-" * 100)

        ctype = "نظري" if entry['CourseType'] == 1 else "عملي"
        room_display = entry.get('RoomName', 'لم تحدد')
        print(f"{entry['Day']:<10} | {entry['StartTime'][:5]}-{entry['EndTime'][:5]:<6} | {entry['CourseName']:<25} | {ctype:<5} | {entry['GroupNum']:<7} | {room_display:<18} | {entry['DoctorName']:<15}")

    final_schedule = schedule_copy
    print("\nالمرحلة 7: اكتملت إعادة توزيع القاعات النظرية (بالمنطق الصحيح).")

# --- نهاية الكود ---