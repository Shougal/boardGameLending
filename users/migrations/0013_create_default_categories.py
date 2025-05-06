from django.db import migrations


def create_default_categories(apps, schema_editor):
    Category = apps.get_model("users", "Category")
    default_categories = [
        {
            "name": "Strategy",
            "description": "Games that prioritize skillful thinking and planning",
        },
        {"name": "Family", "description": "Games suitable for players of all ages"},
        {"name": "Party", "description": "Fun, social games for larger groups"},
        {"name": "Card Game", "description": "Games primarily using cards"},
    ]
    for category in default_categories:
        Category.objects.create(**category)


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0012_category_gamecopy_review_alter_boardgame_options_and_more"),
    ]

    operations = [
        migrations.RunPython(create_default_categories),
    ]
