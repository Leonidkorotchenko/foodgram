from django.contrib.auth import get_user_model
from django.db import models

from foodgram_backend.constants import MAX_SLUG_NAME

User = get_user_model()


class Tag(models.Model):
    name = models.ForeignKey()
    slug = models.SlugField(
        unique=True,
        max_length=MAX_SLUG_NAME,
    )


class Ingredient(models.Model):
    name = models.ForeignKey()
    uom = models.IntegerField()


class Recipe(models.Model):
    author = models.ForeignKey(User, related_name='food',
                               on_delete=models.CASCADE)
    name = models.CharField(max_length=64)
    image = models.ImageField(upload_to='food/image/',
                              null=True, default=None)
    description = (models.TextField(
        verbose_name='Описание',
        blank=True,
        null=True,)
                   )
    ingredient = ()
    tag = models.ForeignKey(Tag,
                            on_delete=models.CASCADE,
                            related_name='recipe',
                            )
    time = ()
