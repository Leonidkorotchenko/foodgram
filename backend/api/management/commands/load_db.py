import json

from django.core.management.base import BaseCommand, CommandError
from tqdm import tqdm

from foodgram_backend.settings import PATH_TO_INGREDIENTS
from api.models import Ingredient


class Command(BaseCommand):
    """Заполнение базы ингридиентами."""

    def handle(self, *args, **options):

        with open(PATH_TO_INGREDIENTS, encoding='UTF-8') as ingredients_file:
            ingredients = json.load(ingredients_file)

            for ingredients in tqdm(ingredients):
                try:
                    Ingredient.objects.get_or_create(**ingredients)
                except CommandError as e:
                    raise CommandError(
                        f'Ошибка {e} при добавлении {ingredients}.')
