from django.db import models
import datetime
import pytz

# Create your models here.


class Event(models.Model):
    """カレンダーのイベント"""
    summary = models.CharField('イベント名', max_length=255)
    unique_id = models.CharField('unique_id', max_length=255)
    start = models.DateTimeField('開始時間')

    def __str__(self):
        return self.summary

    @classmethod
    def get_next_event(cls):
        now = datetime.datetime.now(pytz.timezone('Asia/Tokyo'))
        event = cls.objects.filter(start__gte=now).order_by('start').first()
        event.start = event.start.astimezone(pytz.timezone('Asia/Tokyo'))
        return event

    @classmethod
    def get_next_event_attendee_count(cls):
        next_event = cls.get_next_event()
        return next_event.attendee_set.filter(attend=1).count()


class Attendee(models.Model):
    """参加者"""
    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    user = models.CharField('ユーザー', max_length=255)
    attend = models.IntegerField('参加可否', default=0)

    def __str__(self):
        return self.user

    @classmethod
    def save_postback(cls, user, postback):
        data = postback.split(":")
        event_unique_id = data[0]
        event = Event.objects.filter(unique_id=event_unique_id).first()
        if data[1] == "yes":
            attend = 1
        else:
            attend = 0

        exist_data = cls.objects.filter(event=event, user=user).first()
        if exist_data is None:
            cls(event=event, user=user, attend=attend).save()
        else:
            exist_data.attend = attend
            exist_data.save()
        return


class User(models.Model):
    """ユーザー"""
    user_id = models.CharField('ユーザーID', max_length=255)
    name = models.CharField('名前', max_length=255, default='')
    hiragana_name = models.CharField('読み方', max_length=255, default='')

    def __str__(self):
        return self.name

    @classmethod
    def save_user_id(cls, user_id):
        user = cls.objects.filter(user_id=user_id).first()
        if user:
            user.name = ''
            user.hiragana_name = ''
            user.save()
        else:
            cls(user_id=user_id).save()

    @classmethod
    def save_name(cls, user_id, name):
        user = cls.objects.filter(user_id=user_id).first()
        if user:
            user.name = name
            user.save()

    @classmethod
    def save_hiragana_name(cls, user_id, hiragana_name):
        user = cls.objects.filter(user_id=user_id).first()
        if user:
            user.hiragana_name = hiragana_name
            user.save()


class Match(models.Model):
    """試合結果"""
    my_user = models.ForeignKey(User, related_name='my_user', on_delete=models.CASCADE)
    opponent_user = models.ForeignKey(User, related_name='opponent_user', null=True, blank=True, on_delete=models.CASCADE)
    my_set = models.IntegerField('自分のセット数', null=True, default=None)
    opponent_set = models.IntegerField('相手のセット数', null=True, default=None)
    date = models.DateTimeField('日時')

    def __str__(self):
        return str(self.my_user) + "-" + str(self.opponent_user)
