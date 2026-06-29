web: python -m bot.main polling
worker: celery -A bot.tasks.celery_app worker --loglevel=info --concurrency=2
beat: celery -A bot.tasks.celery_app beat --loglevel=info
