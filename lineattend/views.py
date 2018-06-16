from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt

from lineattend.models import *
from lineattend.forms import EventForm

from apiclient.discovery import build
from httplib2 import Http
from oauth2client.service_account import ServiceAccountCredentials
import datetime
import re
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
            elif request_event['message']['text'] == "名前登録":
                # 苗字を登録させる
                # 空データをUserに挿入
                User.save_user_id(request_event['source']['userId'])
                payload = {
                    "replyToken": reply_token,
                    "messages": [
                        {
                            "type": "text",
                            "text": "苗字を入力してください"
                        }
                    ]
                }
            elif request_event['message']['text'] == "試合結果登録":
                # 相手の苗字を入力して試合結果を登録する
                # 空の試合データを挿入
                my_user = User.objects.filter(user_id=request_event['source']['userId']).first()
                Match(my_user=my_user, date=datetime.datetime.now()).save()
                payload = {
                    "replyToken": reply_token,
                    "messages": [
                        {
                            "type": "text",
                            "text": "相手の苗字をひらがなで入力してください"
                        }
                    ]
                }

            else:
                user_id = request_event['source']['userId']
                user = User.objects.filter(user_id=user_id).first()

                match = Match.objects.filter(my_user=user, my_set__isnull=True).first()

                if user.name == '' and user.hiragana_name == '':
                    User.save_name(user_id, request_event['message']['text'])
                    payload = {
                        "replyToken": reply_token,
                        "messages": [
                            {
                                "type": "text",
                                "text": "苗字の読み方をひらがなで入力してください"
                            }
                        ]
                    }
                elif user.hiragana_name == '' and re.match('^[あ-ん]+$', request_event['message']['text']):
                    User.save_hiragana_name(user_id, request_event['message']['text'])
                    payload = {
                        "replyToken": reply_token,
                        "messages": [
                            {
                                "type": "text",
                                "text": "名前を登録しました"
                            }
                        ]
                    }
                elif match:
                    opponent_user = User.objects.filter(hiragana_name=request_event['message']['text']).first()
                    match.opponent_user = opponent_user
                    match.save()
                    if opponent_user:
                        payload = {
                            "replyToken": reply_token,
                            "messages": [
                                {
                                    "type": "template",
                                    "altText": "This is a buttons tmplete",
                                    "template": {
                                        "type": "buttons",
                                        "text": "あなたのセット数は？",
                                        "actions": [
                                            {
                                                "type": "postback",
                                                "label": "1",
                                                "displayText": "1",
                                                "data": "my_set_regist:1"
                                            },
                                            {
                                                "type": "postback",
                                                "label": "2",
                                                "displayText": "2",
                                                "data": "my_set_regist:2"
                                            },
                                            {
                                                "type": "postback",
                                                "label": "3",
                                                "displayText": "3",
                                                "data": "my_set_regist:3"
                                            },
                                            {
                                                "type": "postback",
                                                "label": "4",
                                                "displayText": "4",
                                                "data": "my_set_regist:4"
                                            }
                                        ]
                                    }
                                }
                            ]
                        }
                    else:
                        payload = {
                            "replyToken": reply_token,
                            "messages": [
                                {
                                    "type": "text",
                                    "text": "対戦相手が見つかりません\nもう一度入力してください"
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
            if request_event['postback']['data'].count("my_set_regist"):
                payload = {
                    "replyToken": reply_token,
                    "messages": [
                        {
                            "type": "template",
                            "altText": "This is a buttons tmplete",
                            "template": {
                                "type": "buttons",
                                "text": "相手のセット数は？",
                                "actions": [
                                    {
                                        "type": "postback",
                                        "label": "1",
                                        "displayText": "1",
                                        "data": "opponent_set_regist:1"
                                    },
                                    {
                                        "type": "postback",
                                        "label": "2",
                                        "displayText": "2",
                                        "data": "opponent_set_regist:2"
                                    },
                                    {
                                        "type": "postback",
                                        "label": "3",
                                        "displayText": "3",
                                        "data": "opponent_set_regist:3"
                                    },
                                    {
                                        "type": "postback",
                                        "label": "4",
                                        "displayText": "4",
                                        "data": "opponent_set_regist:4"
                                    }
                                ]
                            }
                        }
                    ]
                }
            elif request_event['postback']['data'].count("opponent_set_regist"):
                payload = {
                    "replyToken": reply_token,
                    "messages": [
                        {
                            "type": "text",
                            "text": "試合結果を登録しました"
                        }
                    ]
                }
            else:
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
