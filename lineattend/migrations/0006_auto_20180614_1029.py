# Generated by Django 2.0.5 on 2018-06-14 01:29

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('lineattend', '0005_auto_20180612_1427'),
    ]

    operations = [
        migrations.AlterField(
            model_name='match',
            name='my_set',
            field=models.IntegerField(default=None, null=True, verbose_name='自分のセット数'),
        ),
        migrations.AlterField(
            model_name='match',
            name='opponent_set',
            field=models.IntegerField(default=None, null=True, verbose_name='相手のセット数'),
        ),
        migrations.AlterField(
            model_name='match',
            name='opponent_user',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='opponent_user', to='lineattend.User'),
        ),
    ]
