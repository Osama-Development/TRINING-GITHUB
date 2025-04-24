# -*- coding: utf-8 -*-
# ==============================================================================
#              خلية Gradio لعرض الجدول الدراسي - منفصلة (معدلة)
# ==============================================================================
#
# !!! هام جداً !!!
# 1.  تأكد من تشغيل خلية الكود الأساسية التي تحتوي على مراحل 0-6 أولاً.
# 2.  هذه الخلية تعتمد على المتغيرات التي تم إنشاؤها في الخلية السابقة،
#     خصوصاً:
#       - `schedule`: قائمة القواميس التي تمثل الجدول النهائي.
#       - `Departments`: قائمة بيانات الأقسام والمستويات للحصول على الأسماء.
#       - `Days`: قاموس لأسماء الأيام (أو قائمة بترتيب الأيام).
#       - `TimeSlots`: قاموس لبيانات الفترات الزمنية (للتأكيد على الترتيب).
#
# 3.  إذا لم يتم تعريف هذه المتغيرات في البيئة الحالية، سيحدث خطأ.
#
# ==============================================================================

import gradio as gr
import pandas as pd
import collections
import math

# --- 1. التأكد من وجود المتغيرات المطلوبة ---
required_vars = ['schedule', 'Departments', 'Days', 'TimeSlots', 'all_room_data', 'all_doctors_data', 'session_details']
missing_vars = [var for var in required_vars if var not in globals()]

if missing_vars:
    raise NameError(f"المتغيرات التالية غير معرفة من الخلية السابقة: {', '.join(missing_vars)}. يرجى التأكد من تشغيل خلية الكود الأساسية أولاً.")

print("المتغيرات المطلوبة موجودة. جاري إعداد واجهة العرض...")

# --- 2. إعداد البيانات للعرض ---

# الحصول على أسماء الأقسام والمستويات
dept_names = {d['DepartmentID']: d['DepartmentName'] for d in Departments}
level_names = {}
for dept in Departments:
    level_names[dept['DepartmentID']] = {
        lvl['LevelID']: lvl['LevelName'] for lvl in dept['Levels']
    }

# ترتيب الأيام المطلوب للعرض
ordered_days = ['Saturday', 'Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday']
# إنشاء خريطة لترتيب الأيام لفرز البيانات
day_order_map = {day: i for i, day in enumerate(ordered_days)}

# تجميع الجدول حسب القسم والمستوى واليوم
grouped_schedule = collections.defaultdict(lambda: collections.defaultdict(lambda: collections.defaultdict(list)))
department_levels = collections.defaultdict(set) # لتتبع المستويات الموجودة فعليًا في الجدول لكل قسم

# تأكد من فرز الجدول الأصلي أولاً باليوم والوقت
schedule_copy.sort(key=lambda x: (day_order_map.get(x['Day'], 99), x['StartTime']))

for entry in schedule_copy:
    dept_id = entry['DepartmentID']
    level_id = entry['LevelID']
    day_name = entry['Day']

    if day_name in ordered_days:
        grouped_schedule[dept_id][level_id][day_name].append(entry)
        department_levels[dept_id].add(level_id)

# --- 3. تعريف CSS للألوان الجديدة والثيم الداكن ---
# الألوان المعدلة:
# - خلفية عامة داكنة: #1a1a1a
# - تبويبات غير نشطة: #003366 (أزرق داكن) مع نص فاتح (#E0FFFF) وحدود فسفورية (#39FF14)
# - تبويبات نشطة: #00509E (أزرق متوسط) مع نص أبيض (#FFFFFF)
# - خلفية الجدول: #252535 (رمادي داكن مائل للزرقة)
# - رأس الجدول: #004080 (أزرق داكن) مع نص فاتح (#E0FFFF) وحدود فسفورية
# - خلايا الجدول: حدود زرقاء داكنة (#004080) ونص أزرق فاتح جداً (#C0DFFF)

css = """
/* تغيير لون خلفية الواجهة الرئيسي ليكون داكنا */
body, .gradio-container { background-color: #1a1a1a !important; color: #f0f0f0 !important; }

/* تخصيص التبويبات */
.tab-nav button {
    background-color: #003366 !important; /* أزرق داكن للتبويبات */
    color: #E0FFFF !important; /* لون نص فاتح للتبويبات */
    border: 1px solid #39FF14 !important; /* حدود فسفورية */
    border-radius: 5px 5px 0 0 !important;
    margin-right: 3px !important; /* مسافة بسيطة بين التبويبات */
}
.tab-nav button.selected {
    background-color: #00509E !important; /* أزرق متوسط للتبويب النشط */
    color: #FFFFFF !important; /* نص أبيض للتبويب النشط */
    border-bottom: 1px solid #00509E !important; /* إخفاء الحد السفلي للتبويب النشط */
}

/* تخصيص الجداول */
.schedule-table {
    border-collapse: collapse;
    width: 98%; /* تقليل العرض قليلاً لإضافة هامش */
    margin: 15px auto; /* توسيط الجدول وإضافة هوامش */
    border: 2px solid #004080; /* حدود خارجية زرقاء داكنة */
    background-color: #252535; /* خلفية داكنة مائلة للزرقة للجدول */
    box-shadow: 0 2px 5px rgba(0, 80, 158, 0.5); /* ظل خفيف */
}

.schedule-table th {
    background-color: #004080; /* رأس الجدول أزرق داكن */
    color: #E0FFFF; /* نص الرأس أزرق فاتح جداً/أبيض */
    padding: 12px 10px; /* زيادة الحشو قليلاً */
    text-align: center;
    border: 1px solid #39FF14; /* حدود فسفورية للخلايا الرأسية */
    font-weight: bold;
}

.schedule-table td {
    padding: 10px 8px; /* زيادة الحشو قليلاً */
    text-align: center;
    border: 1px solid #004080; /* حدود الخلايا زرقاء داكنة */
    color: #C0DFFF; /* نص أزرق فاتح للخلايا */
    /* لا نحتاج لخلفية هنا لأنها من الجدول الرئيسي */
}

/* إزالة تلوين الصفوف بالتناوب */
/*
.schedule-table tbody tr:nth-child(odd) { ... }
.schedule-table tbody tr:nth-child(even) { ... }
*/

/* تحسينات إضافية */
h1, h2, h3, h4 {
    color: #6495ED !important; /* Cornflower blue للعناوين */
    text-shadow: 1px 1px 2px #000; /* ظل خفيف للنص */
    margin-top: 20px;
    margin-bottom: 10px;
    padding-bottom: 5px;
    border-bottom: 1px solid #00509E; /* خط سفلي للعناوين */
}
h1#main-title { border-bottom: 2px solid #39FF14; } /* خط فسفوري تحت العنوان الرئيسي */

.gradio-markdown p { color: #e0e0e0 !important; line-height: 1.6; }

.empty-day-message {
    color: #FFA07A; /* Light Salmon color for 'no lectures' message */
    font-style: italic;
    padding: 15px;
    text-align: center;
    background-color: #2f2f3f; /* خلفية مختلفة قليلاً للرسالة */
    border: 1px dashed #FFA07A;
    margin: 15px auto;
    width: 95%;
}
"""

# --- 4. دالة لإنشاء جدول HTML ليوم معين (تبقى كما هي) ---
def generate_html_table_for_day(data_for_day, table_class="schedule-table"):
    """
    تأخذ قائمة من مدخلات الجدول ليوم واحد وتُرجع سلسلة HTML للجدول.
    """
    if not data_for_day:
        return "<p class='empty-day-message'>لا توجد محاضرات مجدولة لهذا اليوم.</p>"

    # فرز البيانات حسب وقت البدء للتأكد من الترتيب الزمني داخل اليوم
    data_for_day.sort(key=lambda x: x['StartTime'])

    headers_map = {
        "Time": "الوقت",
        "CourseName": "المقرر",
        "CourseType": "النوع",
        "GroupNum": "مجموعة",
        "RoomName": "القاعة",
        "DoctorName": "المدرس"
    }
    headers = list(headers_map.values())

    html = f'<table class="{table_class}">'
    html += "<thead><tr>"
    for header in headers:
        html += f"<th>{header}</th>"
    html += "</tr></thead>"
    html += "<tbody>"

    for entry in data_for_day:
        time_str = f"{entry['StartTime'][:5]} - {entry['EndTime'][:5]}"
        course_type_str = "نظري" if entry['CourseType'] == 1 else "عملي"

        html += "<tr>"
        html += f"<td>{time_str}</td>"
        html += f"<td>{entry['CourseName']}</td>"
        html += f"<td>{course_type_str}</td>"
        html += f"<td>{entry['GroupNum']}</td>"
        html += f"<td>{entry['RoomName']}</td>"
        html += f"<td>{entry['DoctorName']}</td>"
        html += "</tr>"

    html += "</tbody></table>"
    return html

# --- 5. بناء واجهة Gradio (مع إزالة تبويبات الأيام) ---
print("جاري بناء واجهة Gradio...")
with gr.Blocks(theme=gr.themes.Default(primary_hue="blue"), css=css) as demo:
    gr.Markdown("<h1>الجدول الدراسي للمحاضرات</h1>", elem_id="main-title")
    gr.Markdown("<p>عرض الجداول الدراسية لكل قسم ومستوى. تظهر جداول جميع الأيام متسلسلة لكل مستوى.</p>", elem_id="subtitle")

    with gr.Tabs() as department_tabs:
        sorted_dept_ids = sorted(department_levels.keys())

        for dept_id in sorted_dept_ids:
            dept_name = dept_names.get(dept_id, f"قسم {dept_id}")

            with gr.Tab(dept_name, id=f"dept_{dept_id}"):
                gr.Markdown(f"<h2>{dept_name}</h2>")

                with gr.Tabs() as level_tabs:
                    sorted_level_ids = sorted(list(department_levels[dept_id]))

                    for level_id in sorted_level_ids:
                        level_name = level_names.get(dept_id, {}).get(level_id, f"مستوى {level_id}")

                        # === بداية التعديل: عرض محتوى المستوى مباشرة ===
                        with gr.Tab(level_name, id=f"level_{dept_id}_{level_id}"):
                            gr.Markdown(f"<h3>{level_name}</h3>")

                            # الآن نعرض جداول الأيام متسلسلة هنا بدلاً من تبويبات
                            for day_name in ordered_days:
                                # إضافة عنوان لليوم الحالي
                                gr.Markdown(f"<h4>جدول يوم: {day_name}</h4>")

                                # استرجاع بيانات اليوم
                                day_data = grouped_schedule.get(dept_id, {}).get(level_id, {}).get(day_name, [])

                                # إنشاء وعرض جدول HTML لهذا اليوم
                                html_content = generate_html_table_for_day(day_data)
                                gr.HTML(html_content) # عرض الجدول
                        # === نهاية التعديل ===

# --- 6. تشغيل الواجهة ---
print("جاري تشغيل واجهة Gradio...")
demo.launch(debug=True, share=True, inline=False)
demo.launch() # للاستخدام العادي بدون رابط مشاركة