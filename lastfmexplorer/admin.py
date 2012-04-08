from django.contrib import admin
from models import *

# class UserAdmin(admin.ModelAdmin):
    # pass
# admin.site.register(User, UserAdmin)
admin.site.register(User)
admin.site.register(Update)
admin.site.register(Artist)
admin.site.register(Album)
admin.site.register(Track)
admin.site.register(WeekData)
admin.site.register(WeekTrackData)
admin.site.register(Tag)
admin.site.register(WeeksWithSyntaxErrors)


