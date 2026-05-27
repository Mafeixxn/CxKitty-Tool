"""Course list and detail routes."""

from flask import Blueprint, flash, redirect, render_template, session, url_for

from web.app import get_api

courses_bp = Blueprint("courses", __name__)


@courses_bp.route("/courses")
def list_courses():
    api = get_api()
    if not api:
        flash("请先登录", "error")
        return redirect(url_for("auth.login_page"))

    try:
        classes = api.fetch_classes()
    except Exception as e:
        flash(f"获取课程列表失败: {e}", "error")
        return render_template("error.html", message=f"获取课程列表失败: {e}")

    return render_template("courses.html", classes=classes.classes)


@courses_bp.route("/courses/<int:index>")
def course_detail(index: int):
    api = get_api()
    if not api:
        flash("请先登录", "error")
        return redirect(url_for("auth.login_page"))

    try:
        classes = api.fetch_classes()
        if index < 0 or index >= len(classes.classes):
            flash("课程不存在", "error")
            return redirect(url_for("courses.list_courses"))
        course = classes.classes[index]
        chap = classes.fetch_chapters_by_index(index)
        # Fetch status counts for all chapters
        try:
            chap.fetch_point_status()
        except Exception:
            pass
    except Exception as e:
        flash(f"获取课程信息失败: {e}", "error")
        return redirect(url_for("courses.list_courses"))

    # For each chapter, fetch task points
    chapters_data = []
    for ci in range(len(chap.chapters)):
        ch = chap.chapters[ci]
        try:
            points = chap.fetch_points_by_index(ci)
        except Exception:
            points = []
        chapters_data.append({
            "chapter": ch,
            "points": points,
        })

    return render_template(
        "chapters.html",
        course=course,
        course_index=index,
        chapters=chap.chapters,
        chapters_data=chapters_data,
        total_chapters=len(chap.chapters),
    )
