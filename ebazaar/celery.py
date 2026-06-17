import os
from celery import Celery
from celery.schedules import crontab

# Set Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ebazaar.settings.development')

app = Celery('ebazaar')

app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks from all installed apps
app.autodiscover_tasks()

# app.conf.beat_schedule = {
#     # Daily sales report at 9 AM
#     'daily-sales-report': {
#         'task': 'orders.tasks.generate_daily_sales_report',
#         'schedule': crontab(hour=9, minute=0),  # 9:00 AM every day
#     },
    
#     # Check low stock every 6 hours
#     'check-low-stock': {
#         'task': 'store.tasks.check_low_stock_products',
#         'schedule': crontab(hour='*/6'),  # Every 6 hours
#     },
    
#     # Send abandoned cart emails at 6 PM
#     'abandoned-cart-reminder': {
#         'task': 'orders.tasks.send_abandoned_cart_reminders',
#         'schedule': crontab(hour=18, minute=0),  # 6:00 PM daily
#     },
    
#     # Weekly summary every Monday at 10 AM
#     'weekly-summary': {
#         'task': 'orders.tasks.generate_weekly_summary',
#         'schedule': crontab(day_of_week=1, hour=10, minute=0),  # Monday 10 AM
#     },
# }

@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}')