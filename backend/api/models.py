from django.core import validators
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from users.models import User
from foodgram_backend.constants import INGREDIENT_MIN_AMOUNT_ERROR


class TagIngredientRecipe(models.Model):

    name = models.CharField(
        verbose_name='Название',
        unique=True,
        max_length=200,
    )

    class Meta:
        abstract = True

    def __str__(self):
        return self.name


class Tag(models.Model):
    name = models.CharField(
        verbose_name="Название тега",
        max_length=32,
        unique=True,
    )
    slug = models.SlugField(
        verbose_name="Слаг тега",
        max_length=32,
        unique=True,
    )

    class Meta:
        verbose_name = "Тег"
        verbose_name_plural = "Теги"
        ordering = ("name",)

    def __str__(self):
        return self.name


class Ingredient(TagIngredientRecipe):

    measurement_unit = models.CharField(
        verbose_name="Единица измерения",
        max_length=200,
    )

    class Meta(TagIngredientRecipe.Meta):
        verbose_name = "Ингредиент"
        verbose_name_plural = 'Ингредиенты'
        ordering = ("name",)
        constraints = [
            models.UniqueConstraint(fields=["name", "measurement_unit"],
                                    name="unique_ingredient")
        ]

    def __str__(self):
        return (
            f'{self.name} ({self.measurement_unit})'
        )


class Recipe(models.Model):
    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="recipes"
    )
    name = models.CharField(
        verbose_name='название рецепта',
        max_length=64
    )
    image = models.ImageField(
        verbose_name='Изображение',
        upload_to='recipes/images/%Y/%m/%d/',
        null=True,
        blank=True
    )
    text = models.TextField(
        verbose_name="Описание рецепта",
    )
    ingredients = models.ManyToManyField(
        Ingredient,
        related_name="recipes",
        verbose_name="ингредиенты",
        through="IngredientInRecipe",
    )
    tags = models.ManyToManyField(
        Tag,
        related_query_name="recipes",
        verbose_name="теги",
        blank=True,
    )
    cooking_time = models.PositiveIntegerField(
        verbose_name="Время приготовления",
        validators=[
            MinValueValidator(1),
            MaxValueValidator(3200)
        ],
    )
    pub_date = models.DateTimeField(
        verbose_name="Дата публикации",
        auto_now_add=True,
    )

    class Meta:
        verbose_name = "Рецепт"
        verbose_name_plural = "Рецепты"
        ordering = ("-pub_date",)

    def in_shopping_cart(self, user):
        return self.in_shopping_carts.filter(user=user).exists()

    def is_favorited(self, user):
        return self.in_favorites.filter(user=user).exists()

    def __str__(self):
        return self.name


class IngredientInRecipe(models.Model):

    recipe = models.ForeignKey(
        Recipe,
        related_name='recipe_list',
        verbose_name='Рецепт',
        on_delete=models.CASCADE,
    )

    ingredient = models.ForeignKey(
        Ingredient,
        related_name='ingredient_list',
        verbose_name='Ингредиент',
        on_delete=models.CASCADE,
    )

    amount = models.PositiveSmallIntegerField(
        verbose_name='Количество',
        default=1,
        validators=(
            validators.MinValueValidator(
                1,
                message=INGREDIENT_MIN_AMOUNT_ERROR,
            ),
        ),
    )

    class Meta:
        ordering = ('-id',)
        verbose_name = 'Количество ингредиента'
        constraints = [
            models.UniqueConstraint(
                fields=['ingredient', 'recipe'],
                name='unique_ingredient_recipe'
            )
        ]

    def __str__(self):
        return (
            f'{self.ingredient.name} ({self.ingredient.measurement_unit})'
            f' - {self.amount}'
        )


class ShoppingCart(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='shopping_carts',
        verbose_name='Пользователь'
    )
    recipe = models.ForeignKey(
        Recipe,
        on_delete=models.CASCADE,
        related_name='in_shopping_carts',
        verbose_name='Рецепт'
    )

    class Meta:
        verbose_name = 'список покупок'
        verbose_name_plural = 'Список покупок'

        constraints = (
            models.UniqueConstraint(
                fields=('user', 'recipe'),
                name='unique_shopping_list_recipe'
            ),
        )

    def __str__(self):
        return f'Рецепт {self.recipe} в списке покупок у {self.user}'


class FavoriteAndShoppingCartModel(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        verbose_name='Пользователь',
    )

    recipe = models.ForeignKey(
        'Recipe',
        on_delete=models.CASCADE,
        verbose_name='Рецепт',
    )

    class Meta:
        abstract = True

    def __str__(self):
        return f'{self.user} - {self.recipe}'


class Favorites(FavoriteAndShoppingCartModel):

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="favorites",
        verbose_name="Пользователь",
    )
    recipe = models.ForeignKey(
        Recipe,
        on_delete=models.CASCADE,
        related_name="in_favorites",
        verbose_name="Рецепт",
    )
    pub_date = models.DateTimeField(
        "Дата добавления",
        auto_now_add=True,
    )

    class Meta:
        verbose_name = "Избранное"
        constraints = [  # Добавить ограничение уникальности
            models.UniqueConstraint(
                fields=['user', 'recipe'],
                name='unique_favorite'
            )
        ]
