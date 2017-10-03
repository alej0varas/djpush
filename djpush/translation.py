from modeltranslation.translator import translator, TranslationOptions

from .models import Notification, NotificationCategory


class NotificationTranslationOptions(TranslationOptions):
    fields = ('title', 'body',)


class NotificationCategoryTranslationOptions(TranslationOptions):
    fields = ('name', )


translator.register(Notification, NotificationTranslationOptions)
translator.register(NotificationCategory, NotificationCategoryTranslationOptions)
