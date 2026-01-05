from datetime import datetime
from typing import List

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


db = SQLAlchemy(model_class=Base)

TASK_PERIOD_TYPE_DAILY = "day"
TASK_PERIOD_TYPE_WEEKLY = "week"


class Task(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    points: Mapped[int]
    allowable_per_period: Mapped[int]
    period_type: Mapped[str]
    completions: Mapped[List["TaskCompletion"]] = db.relationship(back_populates="task")

    @property
    def allowable_per_period_readable(self) -> str:
        if self.allowable_per_period == -1:
            return "Unlimited"

        return f"{self.allowable_per_period} per {self.period_type}"


class TaskCompletion(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(db.ForeignKey("task.id"))
    task: Mapped["Task"] = db.relationship(back_populates="completions")
    timestamp: Mapped[datetime] = mapped_column(server_default=db.func.now())
    point_change: Mapped[int]


class UserAttribute(db.Model):
    key: Mapped[str] = mapped_column(primary_key=True)
    value: Mapped[str]
