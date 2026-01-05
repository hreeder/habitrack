import os
from datetime import datetime, time, timedelta
from functools import reduce

from flask import Flask, redirect, render_template, request, url_for
from flask_migrate import Migrate

from habitrack.models import (
    TASK_PERIOD_TYPE_DAILY,
    TASK_PERIOD_TYPE_WEEKLY,
    Task,
    TaskCompletion,
    UserAttribute,
    db,
)

DB_PATH = os.environ.get("DB_PATH", "sqlite:///habitrack.db")

app = Flask(__name__)
print(f"Instance Path {app.instance_path=}")

app.config["SQLALCHEMY_DATABASE_URI"] = DB_PATH
db.init_app(app)
Migrate(app, db)


def get_completable_tasks(tasks, period_type, period_start_expr):
    period_tasks = [task for task in tasks if task.period_type == period_type]

    completions = (
        db.session.execute(
            db.select(TaskCompletion)
            .where(TaskCompletion.timestamp >= period_start_expr)
            .where(TaskCompletion.task_id.in_([task.id for task in period_tasks]))
        )
        .scalars()
        .all()
    )

    completions_by_task = reduce(
        lambda acc, tc: acc.update({tc.task_id: acc.get(tc.task_id, 0) + 1}) or acc,
        completions,
        {},
    )

    output = []

    for task in period_tasks:
        this_task_completions = completions_by_task.get(task.id, 0)
        this_task_allowable = task.allowable_per_period

        completed = this_task_completions >= this_task_allowable

        if this_task_allowable == -1:
            completed = False  # Unlimited completions allowed

        output.append((task, completed))

    return output


def get_tasks():
    tasks = db.session.execute(db.select(Task)).scalars().all()

    # Using a 4am cutoff means that any tasks logged just after midnight still count for the current
    # "waking" day - so any bedtime routines etc will still make sense.
    now = datetime.now()
    if now.hour < 4:
        today_start = datetime.combine((now - timedelta(days=1)).date(), time(4, 0))
    else:
        today_start = datetime.combine(now.date(), time(4, 0))

    # For weekly boundaries, we also need to check if it's before 4am.
    # If so, treat the current time as part of the previous day/week, so the week starts at the most
    # recent Monday 4:00am before the cutoff. This ensures that tasks completed between midnight and
    # 4am count toward the previous week, matching the daily logic.
    week_ref_date = now if now.hour >= 4 else now - timedelta(days=1)
    week_start_date = week_ref_date.date() - timedelta(days=week_ref_date.weekday())
    week_start = datetime.combine(week_start_date, time(4, 0))

    daily_completable = get_completable_tasks(
        tasks, TASK_PERIOD_TYPE_DAILY, today_start
    )
    weekly_completable = get_completable_tasks(
        tasks, TASK_PERIOD_TYPE_WEEKLY, week_start
    )

    print(daily_completable)
    print(weekly_completable)

    return daily_completable, weekly_completable


@app.route("/")
def index():
    daily_completable, weekly_completable = get_tasks()
    recent_completions = (
        db.session.execute(
            db.select(TaskCompletion)
            .order_by(TaskCompletion.timestamp.desc())
            .limit(25)
        )
        .scalars()
        .all()
    )

    attributes = db.session.execute(db.select(UserAttribute)).scalars().all()
    attributes = {attr.key: attr.value for attr in attributes}

    return render_template(
        "index.html",
        daily_tasks=daily_completable,
        weekly_tasks=weekly_completable,
        recent_completions=recent_completions,
        attributes=attributes,
    )


@app.post("/complete")
def complete_task():
    task = db.get_or_404(Task, request.form["task_id"])
    completion = TaskCompletion(task_id=task.id, point_change=task.points)
    db.session.add(completion)
    db.session.commit()
    return redirect(url_for("index"))


@app.route("/tasks/new", methods=["GET", "POST"])
def new_task():
    if request.method == "POST":
        task = Task(**request.form)
        db.session.add(task)
        db.session.commit()
        return redirect(url_for("index"))
    return render_template("new_task.html")
