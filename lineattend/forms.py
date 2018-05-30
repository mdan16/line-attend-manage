from django.forms import ModelForm
from lineattend.models import Event


class EventForm(ModelForm):
    """イベントのフォーム"""
    class Meta:
        model = Event
        fields = ('summary', 'unique_id', 'start', )
