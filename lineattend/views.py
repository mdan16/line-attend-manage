from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt

from lineattend.models import Event, Attendee
from lineattend.forms import EventForm

from apiclient.discovery import build
from httplib2 import Http
from oauth2client.service_account import ServiceAccountCredentials
import datetime
import requests
import json
from dateutil.parser import parse

from lineattend.password.password import *

# Create your views here.


def event_list(request):
    """イベントの一覧"""
    #return HttpResponse('カレンダーの一覧')
    events = Event.objects.all().order_by('id')
    return render(request, 'lineattend/event_list.html', {'events': events})


def event_edit(request, event_id=None):
    """イベントの編集"""
    #return HttpResponse('カレンダーの編集')
    if event_id:
        event = get_object_or_404(Event, pk=event_id)
    else:
        event = Event()

    if request.method == 'POST':
        form = EventForm(request.POST, instance=event)
        if form.is_valid():
            event = form.save(commit=False)
            event.save()
            return redirect('lineattend:event_list')
    else:
        form = EventForm(instance=event)

    return render(request, 'lineattend/event_edit.html', dict(form=form, event_id=event_id))


def event_del(request, event_id):
    """イベントの削除"""
    #return HttpResponse('カレンダーの削除')
    event = get_object_or_404(Event, pk=event_id)
    event.delete()
    return redirect('lineattend:event_list')

def update_event():
    """イベントの取得"""
    # Setup the Calendar API
    SCOPES = 'https://www.googleapis.com/auth/calendar.readonly'
    creds = ServiceAccountCredentials.from_json_keyfile_name(
        'lineattend/google_calendar_key.json',
        scopes=SCOPES
    )
    service = build('calendar', 'v3', http=creds.authorize(Http()))

    # Call the Calendar API
    now = datetime.datetime.utcnow().isoformat() + 'Z' # 'Z' indicates UTC time

    #Get events in one week
    time_max = datetime.datetime.utcnow() + datetime.timedelta(days=7)
    time_max = time_max.isoformat() + 'Z'
    events_result = service.events().list(calendarId=CALENDAR_ID,
                                          timeMin=now,
                                          timeMax=time_max,
                                          singleEvents=True,
                                          orderBy='startTime').execute()
    events = events_result.get('items', [])

    for e in events:
        if 'dateTime' in e['start']:
            start = parse(e['start']['dateTime'])
        else:
            start = parse(e['start']['date'] + ' 00:00:00')
        summary = e['summary']
        unique_id = e['id']

        event_data = Event.objects.filter(unique_id=unique_id).first()
        if event_data is None:
            event_data = Event(summary=summary, unique_id=unique_id, start=start)
            event_data.save()
    return

@csrf_exempt
def api(request):
    """api for line"""
    REPLY_ENDPOINT = 'https://api.line.me/v2/bot/message/reply'

    if request.method == 'POST':
        request_data = json.loads(request.body.decode('utf-8'))
        if "events" in request_data:
            request_event = request_data["events"][0]
            reply_token = request_event["replyToken"]
            update_event()
        else:
            return

        header = {
            "Content-Type": "application/json",
            "Authorization": "Bearer " + CHANNEL_ACCESS_TOKEN,
        }

        if request_event['type'] == 'message':
            # 直近の予定を取得
            next_event = Event.get_next_event()
            next_event_string = next_event.summary + "\n" + next_event.start.strftime("%Y-%m-%d %H:%M:%S")
            if request_event['message']['text'] == "出欠確認":
                # 確認テンプレートを送信
                payload = {
                    "replyToken": reply_token,
                    "messages": [
                        {
                            "type": "template",
                            "altText": "this is a confirm template",
                            "template": {
                                "type": "confirm",
                                "text": "参加しますか？\n" + next_event_string,
                                "actions": [
                                    {
                                        "type": "postback",
                                        "label": "いいえ",
                                        "data": next_event.unique_id + ":no"
                                    },
                                    {
                                        "type": "postback",
                                        "label": "はい",
                                        "data": next_event.unique_id + ":yes"
                                    }
                                ]
                            },

                        }
                    ]
                }
            elif request_event['message']['text'] == "参加人数確認":
                # 参加人数を通知
                attendee_count = Event.get_next_event_attendee_count()
                payload = {
                    "replyToken": reply_token,
                    "messages": [
                        {
                            "type": "text",
                            "text": next_event_string + "\n参加人数:" + str(attendee_count)
                        }
                    ]
                }
            else:
                payload = {
                    "replyToken": reply_token,
                    "messages": [
                        {
                            "type": "text",
                            "text": "不正な送信です"
                        }
                    ]
                }
        elif request_event['type'] == 'postback':
            # 参加の登録
            user = request_event['source']['userId']
            Attendee.save_postback(user, request_event['postback']['data'])
            # 確認テンプレートのpostbackへの応答
            payload = {
                "replyToken": reply_token,
                "messages": [
                    {
                        "type": "text",
                        "text": "登録しました"
                    }
                ]
            }
        requests.post(REPLY_ENDPOINT, headers=header, data=json.dumps(payload))
    return HttpResponse(status=200)
