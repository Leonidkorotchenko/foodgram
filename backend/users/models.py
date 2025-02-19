from django.contrib.auth.models import AbstractUser
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.core.exceptions import ValidationError
from django.db import models

from foodgram_backend.constants import (MAX_LENGTH_USER,
                                        MAX_LENGTH_USER_EMAIL,)


class User(AbstractUser):

    first_name = models.CharField(
        max_length=MAX_LENGTH_USER,
        verbose_name='имя',
        blank=False
    )

    last_name = models.CharField(
        max_length=MAX_LENGTH_USER,
        verbose_name='фамилия',
        blank=False
    )

    avatar = models.ImageField()

    username = models.CharField(
        max_length=MAX_LENGTH_USER,
        verbose_name='Имя пользователя',
        unique=True,
        validators=[UnicodeUsernameValidator()],
    )

    email = models.EmailField(
        max_length=MAX_LENGTH_USER_EMAIL,
        verbose_name='email',
        unique=True
    )

    REQUIRED_FIELDS = ("username", "first_name", "last_name")
    USERNAME_FIELD = "email"

    class Meta:
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"
        ordering = ("username",)

    def __str__(self):
        return self.username


class Follow(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='follower',
        verbose_name='Подписчик',
    )
    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='following',
        verbose_name='Автор',
    )

    class Meta:
        verbose_name = 'Подписка'
        ordering = ('user',)
        constraints = [
            models.UniqueConstraint(
                fields=('user', 'author'),
                name='unique_follow'
            ),
            models.CheckConstraint(
                check=~models.Q(author=models.F('user')),
                name='no_self_follow'
            )
        ]

    def __str__(self):
        return f'Пользователь {self.user} подписан на {self.author}'

    def delete(self, *args, **kwargs):
        if not Follow.objects.filter(pk=self.pk).exists():
            raise ValidationError('Подписка не существует')
        super().delete(*args, **kwargs)
