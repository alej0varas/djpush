from django import forms
from django.conf import settings
from django.contrib import admin
from django.db.models import TextField


# If django-modeltranslation is installed we show translations
try:
    from modeltranslation.admin import TabbedTranslationAdmin
except ImportError:
    TabbedTranslationAdmin = admin.ModelAdmin


from . import models


class NotificationSchedulerInline(admin.TabularInline):
    model = models.NotificationScheduler


class NotifcationCategoryAdmin(TabbedTranslationAdmin):
    list_display = ('name', 'opt_out')


class NotificationAdminForm(forms.ModelForm):
    class Meta:
        model = models.Notification
        widgets = {
            'slug': forms.Select(
                choices=settings.DJPUSH_NOTIFICATION_CHOISES)
        }
        fields = '__all__'


class NotificationAdmin(TabbedTranslationAdmin):
    form = NotificationAdminForm
    list_display = ('name', 'slug', 'enabled', 'category')
    formfield_overrides = {
        TextField: {'widget': forms.TextInput}
    }

    fieldsets = (
        ("General", {
            'fields': (
                'name',
                'enabled',
                'slug',
                'description',
                'category', )
        }),
        ("Common fields", {
            'fields': (
                'title',
                'body',
                'sound',
                'priority', )
        }),
        ('Apple(APNs) fields', {
            'fields': (
                'apns_alert_title_loc_key',
                'apns_alert_title_loc_args',
                'apns_alert_loc_key',
                'apns_alert_log_args',
                'apns_alert_action_loc_key',
                'apns_alert_launch_image',
                'apns_custom', )
        }),
        ('Google(GCM) fields', {
            'fields': (
                'gcm_notification_icon',
                'gcm_notification_tag',
                'gcm_notification_color',
                'gcm_notification_click_action',
                'gcm_notification_body_loc_key',
                'gcm_notification_body_loc_args',
                'gcm_notification_title_loc_key',
                'gcm_notification_title_loc_args',
                'gcm_data', )
        }),
        ('GCM options', {
            'fields': (
                'gcm_option_collapse_key',
                'gcm_option_content_available',
                'gcm_option_delay_while_idle',
                'gcm_option_time_to_live',
                'gcm_option_restricted_package_name', )
        }),
        ('One Signal fields', {
            'fields': (
                'os_template_id', )
        }),
    )

    inlines = [
        NotificationSchedulerInline,
    ]


class NotificationInstanceAdmin(admin.ModelAdmin):
    list_display = ('notification', 'tokens', 'scheduled_at', 'canceled', 'result')
    list_filter = ('notification', 'canceled')
    date_hierarchy = 'scheduled_at'


admin.site.register(models.NotificationCategory, NotifcationCategoryAdmin)
admin.site.register(models.Notification, NotificationAdmin)
admin.site.register(models.NotificationInstance, NotificationInstanceAdmin)
admin.site.register(models.SchedulerInTimeRange)
admin.site.register(models.SchedulerMinutesLater)
