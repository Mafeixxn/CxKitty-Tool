"""Exam question viewing routes."""

from flask import Blueprint, flash, redirect, render_template, session, url_for

from web.app import get_api

exam_bp = Blueprint("exam", __name__)

QUESTION_TYPE_NAMES = {
    0: "单选题", 1: "多选题", 2: "填空题", 3: "判断题", 4: "简答题",
    5: "名词解释", 6: "论述题", 7: "计算题", 8: "其它", 9: "分录题",
    10: "资料题", 11: "连线题", 13: "排序题", 14: "完型填空",
    15: "阅读理解", 18: "口语题", 19: "听力题",
}


@exam_bp.route("/courses/<int:course_index>/exams/<int:ch_index>/<int:pt_index>")
def view_exam(course_index: int, ch_index: int, pt_index: int):
    api = get_api()
    if not api:
        flash("请先登录", "error")
        return redirect(url_for("auth.login_page"))

    try:
        classes = api.fetch_classes()
        if course_index < 0 or course_index >= len(classes.classes):
            flash("课程不存在", "error")
            return redirect(url_for("courses.list_courses"))
        course = classes.classes[course_index]
        chap = classes.fetch_chapters_by_index(course_index)
        if ch_index < 0 or ch_index >= len(chap.chapters):
            flash("章节不存在", "error")
            return redirect(url_for("courses.course_detail", index=course_index))
        chapter = chap.chapters[ch_index]
        points = chap.fetch_points_by_index(ch_index)
        if pt_index < 0 or pt_index >= len(points):
            flash("任务点不存在", "error")
            return redirect(url_for("courses.course_detail", index=course_index))
        point = points[pt_index]

        if point.__class__.__name__ != "ChapterExam":
            flash("该任务点不是测验", "error")
            return redirect(url_for("courses.course_detail", index=course_index))

        # Load exam data
        prefetch_ok = point.pre_fetch()
        fetch_ok = point.fetch()

        if not fetch_ok:
            flash("无法加载试题（可能已批阅、无权限，或页面结构变化）", "error")
            return redirect(url_for("courses.course_detail", index=course_index))

        return render_template(
            "exam.html",
            course=course,
            course_index=course_index,
            chapter=chapter,
            exam=point,
            questions=point.questions,
            title=getattr(point, "title", "未知测验"),
            question_types=QUESTION_TYPE_NAMES,
        )
    except Exception as e:
        flash(f"加载试题失败: {e}", "error")
        return redirect(url_for("courses.course_detail", index=course_index))
