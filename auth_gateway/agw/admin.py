from django.contrib import admin
from agw.models import Player
# Register your models here.
class PlayerAdmin(admin.ModelAdmin):
    model = Player


class MemberInline(admin.TabularInline):
    model = Player


admin.site.register(Player, PlayerAdmin)
