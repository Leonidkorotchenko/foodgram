from django.contrib.auth import get_user_model
from django.db import models

from ..foodgram_backend.constants import MAX_NAME_LENGTH, MAX_SLUG_NAME

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


class User(AbstractUser):

    username = models.CharField(
        max_length=150,
        verbose_name='Имя пользователя',
        unique=True,
        db_index=True,
        validators=[RegexValidator(
            regex=r'^[\w.@+-]+$',
            message='В имени пользователя недопустимый символ'
        )]
    )
    email = models.EmailField(
        max_length=254,
        verbose_name='email',
        unique=True
    )
    first_name = models.CharField(
        max_length=150,
        verbose_name='имя',
        blank=True
    )
    last_name = models.CharField(
        max_length=150,
        verbose_name='фамилия',
        blank=True
    )
    bio = models.TextField(
        verbose_name='биография',
        blank=True
    )
    role = models.CharField(
        max_length=20,
        verbose_name='роль',
        choices=UserRoles.choices(),
        default=UserRoles.user.name
    )

    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'
        ordering = ('id',)

    @property
    def is_admin(self):
        return self.role == UserRoles.admin.name

    @property
    def is_moderator(self):
        return self.role == UserRoles.moderator.name

    @property
    def is_user(self):
        return self.role == UserRoles.user.name
