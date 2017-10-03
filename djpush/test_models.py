import datetime
import json
from unittest import mock

from django.test import TestCase
import pypn
import pytz

from . import models


tz = pytz.timezone('Europe/Paris')


class SendTestCase(TestCase):
    def test_success_apns(self):
        notification = models.Notification.objects.create(slug='a-slug', enabled=True)
        tokens = '["token", "token1"]'
        data = '{}'
        notification_instance = models.NotificationInstance.objects.create(notification=notification, tokens=tokens, data=data, provider=pypn.DUMMY)
        with mock.patch('djpush.models.pypn.Notification.send') as mock_send:
            response_mock = mock.Mock()
            response_mock.status_code = 200
            response_mock.json.return_value = {
                "id": "458dcec4-cf53-11e3-add2-000c2940e62c",
                "recipients": 3
            }
            mock_send.return_value = response_mock

            notification_instance.send()

            mock_send.assert_called_once_with(json.loads(tokens), json.loads(data))


class NotificationTestCase(TestCase):
    def test_as_dict(self):
        context = {'username': 'yahoo', 'emoji': '😎'}
        notification = models.Notification(
            title='hello {{ username }}!',
            body='you are the best! {{ emoji }}')

        keys = notification.as_dict(context=context)
        for key in keys:
            self.assertNotIn('scheduler', key)

        excluded = ['name', 'slug', 'description', 'enabled']
        for key_excluded in excluded:
            self.assertNotIn(key_excluded, keys)
        self.assertIn(context['username'], keys['title']['en'])
        self.assertIn(context['emoji'], keys['body']['en'])
        self.assertIn('data', keys)
        self.assertIn('notification_id', keys['data'])
        self.assertEqual(notification.slug, keys['data']['notification_id'])


class SchedulerTestCase(TestCase):
    def test_get_child_scheduler(self):
        child_scheduler = models.SchedulerInTimeRange.objects.create(
            start_hour=8, end_hour=22)
        scheduler = models.Scheduler.objects.get()

        result = scheduler.get_child_scheduler()

        self.assertEqual(result, child_scheduler)

    def test_get_child_scheduler_does_not_exist(self):
        scheduler = models.Scheduler.objects.create()

        result = scheduler.get_child_scheduler()

        self.assertEqual(result, None)

    def test_get_schedule(self):
        # No child scheduler
        expected_result = datetime.datetime.now().replace(microsecond=0)

        result = models.Scheduler().get_schedule(datetime.datetime.now()).replace(microsecond=0)

        self.assertEqual(result, expected_result)

        # With child scheduler
        now = datetime.datetime.now().replace(microsecond=0)
        scheduler_args = (1, 2)
        mock_instance = mock.Mock()
        mock_class = mock.Mock()
        mock_class.return_value = mock_instance
        mock_get_args = mock.Mock()
        mock_get_args.return_value = scheduler_args
        mock_scheduler = mock.Mock()
        mock_scheduler.scheduler_class = mock_class
        mock_scheduler.get_scheduler_args = mock_get_args
        mock_get_child = mock.Mock()
        mock_get_child.return_value = mock_scheduler
        models.Scheduler.get_child_scheduler = mock_get_child

        models.Scheduler().get_schedule(now).replace(microsecond=0)

        mock_get_child.assert_called_once_with()
        mock_get_args.assert_called_once_with()
        mock_class.assert_called_once_with(*scheduler_args)
        mock_instance.assert_called_once_with(now)


class ScheduleNotificationTestCase(TestCase):
    @mock.patch('djpush.models.send_notification_task')
    def test_success(self, mock_send):
        slug = 'a-slug'
        tokens = ['token', 'token1']
        timezone = pytz.timezone('Europe/Paris')
        scheduler = models.SchedulerInTimeRange.objects.create(start_hour=21, end_hour=22)
        notification = models.Notification.objects.create(slug=slug, enabled=True)
        models.NotificationScheduler.objects.create(notification=notification, scheduler=scheduler, order=0)
        context = {'any': 'value'}

        with mock.patch('djpush.models.Notification.as_dict') as mock_as_dict:
            mock_as_dict.return_value = {'body': 'who cares'}
            result = models.schedule_notification(timezone, slug, tokens, context)

        self.assertIsNotNone(result)
        mock_as_dict.assert_called_once_with(context)

    def test_scheduler_discard(self):
        slug = 'a-slug'
        tokens = ['token', 'token1']
        timezone = pytz.timezone('Europe/Paris')
        scheduler = models.SchedulerInTimeRange.objects.create(start_hour=8, end_hour=22, discard=True)
        notification = models.Notification.objects.create(slug=slug, enabled=True)
        models.NotificationScheduler.objects.create(notification=notification, scheduler=scheduler, order=0)

        with mock.patch('djpush.models.SchedulerInTimeRange.scheduler_class.__call__') as mock_call:
            mock_call.return_value = None
            result = models.schedule_notification(timezone, slug, tokens)

        self.assertIsNone(result)


class TasksTestCase(TestCase):
    def test_send_notification_task(self):
        tokens = '["token", "token1"]'
        notification = models.Notification.objects.create()
        notification_instance = models.NotificationInstance.objects.create(notification=notification, tokens=tokens, data='{}')
        with mock.patch('djpush.models.NotificationInstance.send') as mock_send:

            models.send_notification_task(notification_instance.pk)

            mock_send.assert_called_once_with()
