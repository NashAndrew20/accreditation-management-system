from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accreditation', '0004_areaassignment'),
    ]

    operations = [
        migrations.AlterField(
            model_name='areaassignment',
            name='deadline',
            field=models.DateField(blank=True, null=True),
        ),
    ]
