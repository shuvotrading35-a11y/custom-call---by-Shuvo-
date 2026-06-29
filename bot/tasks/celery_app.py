"""
bot/tasks/celery_app.py  (also used as scheduler/celery_app.py)
Celery application instance
"""

from celery import Celery

from bot.config.settings import settings

celery_app = Celery(
    "callbot",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "bot.tasks.call_tasks",
        "bot.tasks.bulk_tasks",
        "bot.tasks.payment_tasks",
        "bot.tasks.cleanup_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Dhaka",
    enable_utc=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_reject_on_worker_lost=True,
    task_soft_time_limit=300,    # 5 min soft
    task_time_limit=600,         # 10 min hard
    result_expires=3600,
    beat_schedule={
        "cleanup-old-logs": {
            "task": "bot.tasks.cleanup_tasks.cleanup_old_logs",
            "schedule": 86400,   # daily
        },
        "referral-reward-processor": {
            "task": "bot.tasks.payment_tasks.process_pending_referrals",
            "schedule": 3600,    # hourly
        },
    },
)
