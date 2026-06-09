from django.db import migrations, models

import answer.models


class Migration(migrations.Migration):
    dependencies = [
        ("answer", "0004_drop_answer_document_add_indexes"),
    ]

    operations = [
        migrations.AddField(
            model_name="document",
            name="original_name",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AlterField(
            model_name="document",
            name="uploaded_file",
            field=models.FileField(upload_to=answer.models.document_upload_path),
        ),
    ]
