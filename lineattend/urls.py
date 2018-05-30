from django.conf.urls import url
from . import views
from django.urls import path, include

app_name = 'lineattend'
urlpatterns = [
    path('event/', views.event_list, name='event_list'),
    path('event/edit/<int:event_id>/', views.event_edit, name='event_edit'),
    path('event/del/<int:event_id>/', views.event_del, name='event_del'),
    path('api/event/', views.api, name='api')
]
