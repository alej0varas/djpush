from collections import defaultdict
import datetime
import json

import pypn
import requests
from celery import shared_task
from django.conf import settings
from django.core.exceptions import (ImproperlyConfigured,
                                    ObjectDoesNotExist, ValidationError)
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.template import Context, Template
from timezone_field import TimeZoneField

from . import schedulers


PRIORITY_NORMAL = 'normal'
PRIORITY_HIGH = 'high'
PRIORITY_CHOICES = (
    (PRIORITY_NORMAL, "Normal"),
    (PRIORITY_HIGH, "High"),
)
SEND_NOTIFICATION_KWARGS = {}

DEFAULT_PROVIDER = getattr(settings, 'DJPUSH_DEFAULT_PROVIDER')
if DEFAULT_PROVIDER is None:
    raise ImproperlyConfigured(
        'A default notification provider is required. '
        'Check README for details.')

try:
    _expires = int(getattr(settings, 'DJPUSH_NOTIFICATION_EXPIRES'))
    SEND_NOTIFICATION_KWARGS.update({'expires': _expires})
except (AttributeError, TypeError, ValueError):
    pass


try:
    NOTIFICATION_CHOICES = getattr(settings, 'DJPUSH_NOTIFICATION_CHOISES')
except AttributeError:
    NOTIFICATION_CHOICES = []

# Should always exist because it's a Django default
try:
    LANGUAGES = dict(getattr(settings, 'LANGUAGES')).keys()
except AttributeError:
    LANGUAGES = []


class NotificationCategory(models.Model):
    name = models.CharField(max_length=100)
    opt_out = models.BooleanField(default=False, help_text="If checked the "
                                  "user can opt-out receiving this category")

    def __str__(self):
        return self.name


def ValidNotificationSlug(value):
    if value not in [i[0] for i in NOTIFICATION_CHOICES]:
        raise ValidationError('%s not in "DJPUSH_NOTIFICATION_CHOISES"'
                              % value)


class Notification(models.Model):
    """The notification definition. Includes all possible fields used by
    APNs and GCM

    """
    name = models.CharField(max_length=100)
    enabled = models.BooleanField(default=False, help_text="The notification "
                                  "will not be sent if this is unchecked")
    slug = models.SlugField(
        unique=True,
        validators=[ValidNotificationSlug, ]
    )
    description = models.TextField()
    category = models.ForeignKey(NotificationCategory, null=True, blank=True)

    #
    # Shared fields
    #
    title = models.TextField(default='', blank=True)
    body = models.TextField(default='', blank=True)
    sound = models.TextField(default='', blank=True)
    priority = models.CharField(
        max_length=20,
        choices=PRIORITY_CHOICES, default=PRIORITY_HIGH,
        help_text="Valid values are \"normal\" and \"high.\". In APNs 5 and 10"
    )

    #
    # APNs fields
    #

    # APNs Alert fields
    # If defined, those fields make the alert a JSON object and not a string
    apns_alert_title_loc_key = models.TextField(default='', blank=True)
    apns_alert_title_loc_args = models.TextField(default='', blank=True)
    apns_alert_loc_key = models.TextField(default='', blank=True)
    apns_alert_log_args = models.TextField(default='', blank=True)
    apns_alert_action_loc_key = models.TextField(default='', blank=True)
    apns_alert_launch_image = models.TextField(default='', blank=True)

    # APNs custom data
    apns_custom = models.TextField(default='', blank=True)

    #
    # GCM fields
    #

    # GCM notification fields
    gcm_notification_icon = models.TextField(default='', blank=True)
    gcm_notification_tag = models.TextField(default='', blank=True)
    gcm_notification_color = models.TextField(default='', blank=True)
    gcm_notification_click_action = models.TextField(default='', blank=True)
    gcm_notification_body_loc_key = models.TextField(default='', blank=True)
    gcm_notification_body_loc_args = models.TextField(default='', blank=True)
    gcm_notification_title_loc_key = models.TextField(default='', blank=True)
    gcm_notification_title_loc_args = models.TextField(default='', blank=True)

    # GCM options fields
    gcm_option_collapse_key = models.TextField(default='', blank=True)
    gcm_option_content_available = models.TextField(default='', blank=True)
    gcm_option_delay_while_idle = models.BooleanField(
        default=False,
        help_text="When this parameter is set to true, it indicates that the "
                  "message should not be sent until the device becomes active."
    )

    gcm_option_time_to_live = models.IntegerField(
        null=True,
        blank=True,
        validators=[MaxValueValidator(pypn.four_weeks_in_seconds)],
        help_text="This parameter specifies how long (in seconds) the message "
                  "should be kept in GCM storage if the device is offline. "
                  "The maximum time to live supported is 4 weeks"
    )
    gcm_option_restricted_package_name = models.TextField(
        default='', blank=True)
    # GCM custom data
    gcm_data = models.TextField(
        default='',
        blank=True,
        help_text="This parameter specifies the custom key-value pairs of the "
                  "message's payload."
    )

    # OneSignal custom fields
    os_template_id = models.TextField(default='', blank=True)

    def as_dict(self, context=None):
        context = context or {}
        # Fields we want to render
        dynamic_keys = ['body', 'title']
        # To get translations
        fields = [field for field in self._meta.get_fields()]
        # Exclude administrative fields
        excluded_keys = ['id', 'name', 'slug', 'description', 'enabled',
                         'notificationscheduler', 'notificationinstance',
                         'category']
        # Exclude translation fields
        for field in fields:
            if field.name.split('_')[-1] in LANGUAGES:
                excluded_keys.append(field.name)
        # Data to pass to pypn
        result = {}
        for field in fields:
            if field.name in excluded_keys:
                continue
            result[field.name] = getattr(self, field.name)
        # Translate fields
        context = Context(context)
        dynamic_fields = defaultdict(dict)
        for field in dynamic_keys:
            # If translation *is not* enabled, we need a default 'en'
            try:
                template = Template(getattr(self, field))
                dynamic_fields[field]['en'] = template.render(context)
            except AttributeError:
                pass
            # If translation *is* enabled
            for language in LANGUAGES:
                try:
                    template = Template(getattr(self, field + '_' + language))
                except AttributeError:
                    continue
                dynamic_fields[field][language] = template.render(context)
        if dynamic_fields['body']['en']:
            result.update(dynamic_fields)
        if not result['body']:
            result.pop('body')
        # Add custom data
        result.update({'data': {'notification_id': self.slug}})

        return result

    def __str__(self):
        return self.name


class NotificationScheduler(models.Model):
    """A notification could have more than one scheduler. Schedulers are
    applied in order. Order of schedulers is important in some
    cases. If we apply `SchedulerMinutesLater` then
    `SchedulerInTimeRange` is different from `SchedulerInTimeRange`
    then `SchedulerMinutesLater`. If now is 21:59, fixed time is 5
    minutes and working hours are from 8:00 to 22:00. In the first
    case the result is "tomorrow at 8:00" because now plus fixed is
    *not* in working hours. In the second case we get "today at 22:04"
    because now *is* in working hours and we add the fixed.

    """
    notification = models.ForeignKey(Notification)
    scheduler = models.ForeignKey(
        'djpush.Scheduler',
        help_text="No scheduler means the notification will be sent "
                  "immediately",
    )
    order = models.IntegerField()

    class Meta:
        unique_together = ('notification', 'scheduler', 'order')


class NotificationInstance(models.Model):
    """The notification as it is sent to the provider"""
    notification = models.ForeignKey(Notification)

    # Data required to send the notification
    provider = models.CharField(max_length=20)
    # They must only contain valid json
    tokens = models.TextField()
    data = models.TextField()
    scheduled_at = models.DateTimeField(null=True)
    canceled = models.BooleanField(default=False)

    # For the record, not needed at all
    timezone = TimeZoneField()
    sent_at = models.DateTimeField(null=True)
    result = models.TextField(default='', blank=True)

    def send(self):
        if self.canceled:
            return None
        # Avoid sending the notification again if the worker runs the
        # same task multiple times. It's happening with celery and AWS
        # SQS.
        if self.sent_at is not None:
            return None
        notification = pypn.Notification(self.provider)
        result = notification.send(json.loads(self.tokens),
                                   json.loads(self.data))
        self.sent_at = datetime.datetime.now()
        # This should be handled by pypn. `result` can be `None`,
        # <str>, <requests.Response>(OneSignal) We only use OneSignal
        # so we will consider it's a `Response` that contains json.
        if result.status_code == requests.codes.ok:
            self.result = result.json()
        else:
            self.result = result.content
        self.save(update_fields=('sent_at', 'result'))

        return result


class Scheduler(models.Model):
    """Parent class for schedulers. It's used by a foreign key in
    `Notification`.

    """
    def __str__(self):
        """Get the representation from the corresponding child"""
        scheduler = self.get_child_scheduler()
        return str(scheduler)

    def get_child_scheduler(self):
        childs_names = [name for name in dir(self)
                        if name.startswith('scheduler')]
        obj = None
        for name in childs_names:
            try:
                # There is only one child per instance. Once we get it
                # we stop iterating
                obj = getattr(self, name)
                break
            except ObjectDoesNotExist:
                pass
        return obj

    def get_schedule(self, now):
        scheduler = self.get_child_scheduler()
        # If no scheduler we schedule for `now`
        if scheduler is None:
            return now
        schedule = scheduler.scheduler_class(
            *scheduler.get_scheduler_args())(now)
        return schedule


class SchedulerInTimeRange(Scheduler):
    scheduler_class = schedulers.SchedulerInTimeRange
    start_hour = models.IntegerField(
        null=True,
        validators=[MinValueValidator(0), MaxValueValidator(23)],
        blank=True)
    end_hour = models.IntegerField(
        null=True,
        validators=[MinValueValidator(0), MaxValueValidator(23)],
        blank=True)
    discard = models.BooleanField(
        default=False, help_text="If checked the notification will be "
        "discarded instead of being scheduling to be sent later")

    def __str__(self):
        return 'Schedule between {} and {} (discard {})'.format(
            self.start_hour, self.end_hour, self.discard)

    def get_scheduler_args(self):
        return self.start_hour, self.end_hour, self.discard


class SchedulerMinutesLater(Scheduler):
    scheduler_class = schedulers.SchedulerMinutesLater
    minutes = models.IntegerField()

    def __str__(self):
        return 'Schedule in {} minute(s)'.format(self.minutes)

    def get_scheduler_args(self):
        return (self.minutes, )


def schedule_notification(timezone, slug, tokens, context=None, provider=None):
    # We sort `tokens` to be sure they will be equal if the same
    # notification is scheduled again. Required to cancel other
    # notifications later.
    tokens = json.dumps(sorted(tokens))
    provider = provider or DEFAULT_PROVIDER
    try:
        notification = Notification.objects.get(slug=slug, enabled=True)
    except Notification.DoesNotExist:
        return None

    # Apply the timezone
    schedule = datetime.datetime.now(timezone)
    # Apply notification schedulers
    schedulers = notification.notificationscheduler_set.all().order_by('order')
    for scheduler in schedulers:
        schedule = scheduler.scheduler.get_schedule(schedule)
    # Remove the timezone. `utctimetuple` returns (2017, 3, 8, 14, 42,
    # 21, 2, 67, 0) so from the beginning to the 5th element is from
    # year to seconds
    TO_SECONDS = 6
    if schedule is not None:
        schedule = datetime.datetime(*schedule.utctimetuple()[:TO_SECONDS])
    # We discard the notification when `delay` equals to `None`
    if schedule is None:
        return None

    # Check for instances with the same `notification` and `tokens` in
    # the same period(between `now` and `schedule`). If none has been
    # sent cancel all of them and schedule current. If any was sent
    # cancel all others and don't schedule current.
    start_date = datetime.datetime.now()
    instances = NotificationInstance.objects.select_for_update(
    ).filter(
        notification=notification,
        tokens=tokens,
        scheduled_at__range=(start_date, schedule)
    )
    any_sent = instances.exclude(
        sent_at__isnull=True
    ).count()
    if any_sent:
        instances.filter(
            sent_at__isnull=True
        ).update(
            canceled=True)
        # Already sent, we don't schedule
        return None
    else:
        # Cancel other not sent notifications
        instances.update(canceled=True)

    # Schedule new notification
    data = json.dumps(notification.as_dict(context))
    notification_instance = NotificationInstance.objects.create(
        notification=notification,
        # data is not the same as notification.data, if dynamic values
        # or translation is applied
        data=data,
        provider=provider,
        tokens=tokens,
        timezone=timezone,
        scheduled_at=schedule,
    )

    # We round because `total_seconds` returns a `float`
    delay = round((schedule - datetime.datetime.now()).total_seconds())
    kwargs = SEND_NOTIFICATION_KWARGS.copy()
    kwargs.update({'countdown': delay})
    result = send_notification_task.apply_async(
        (notification_instance.pk,),
        **kwargs)
    return result


@shared_task
def send_notification_task(pk):
    try:
        notification_instance = NotificationInstance.objects.get(pk=pk)
    except NotificationInstance.DoesNotExist:
        return None
    notification_instance.send()
