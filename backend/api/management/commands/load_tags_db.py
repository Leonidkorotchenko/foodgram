import json

from django.core.management.base import BaseCommand, CommandError
from tqdm import tqdm

from foodgram_backend.settings import PATH_TO_TAGS
from api.models import Tag


class Command(BaseCommand):
    """Заполнение базы ингридиентами."""

    def handle(self, *args, **options):

        with open(PATH_TO_TAGS, encoding='UTF-8') as tags_file:
            tags = json.load(tags_file)

            for tags in tqdm(tags):
                try:
                    Tag.objects.get_or_create(**tags)
                except CommandError as e:
                    raise CommandError(
                        f'Ошибка {e} при добавлении {tags}.')
