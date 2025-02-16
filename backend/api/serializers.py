import base64

from django.db import models, transaction
from django.core.files.base import ContentFile
from rest_framework import serializers, exceptions, status, relations
from rest_framework.exceptions import PermissionDenied
from rest_framework.validators import UniqueTogetherValidator
from users.models import User, Follow
from .models import (
    Recipe,
    Tag,
    Ingredient,
    IngredientInRecipe,
    Favourites
)
from foodgram_backend.constants import INGREDIENT_MIN_AMOUNT_ERROR


class Base64ImageField(serializers.ImageField):
    """Кастомное поле для обработки изображений в формате base64."""

    def to_internal_value(self, data):
        if isinstance(data, str) and data.startswith("data:image"):
            try:
                format, imgstr = data.split(";base64,")
                ext = format.split("/")[-1]
                data = ContentFile(base64.b64decode(imgstr),
                                   name=f"temp.{ext}")
            except Exception:
                raise serializers.ValidationError(
                    "Некорректный формат изображения.")
        return super().to_internal_value(data)


class UserSerializer(serializers.ModelSerializer):
    """Сериализатор пользователя."""

    first_name = serializers.CharField(required=True)
    last_name = serializers.CharField(required=True)
    is_subscribed = serializers.SerializerMethodField(read_only=True)
    avatar = Base64ImageField(required=False, allow_null=True)

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "first_name",
            "last_name",
            "email",
            "is_subscribed",
            "avatar",
        )

    def create(self, validated_data):
        """Создает нового пользователя."""
        user = User.objects.create_user(**validated_data)
        return user


class AvatarSerializer(serializers.ModelSerializer):
    avatar = Base64ImageField()

    class Meta:
        model = User
        fields = ("avatar",)


class FollowSerializer(UserSerializer):
    recipes = serializers.SerializerMethodField(read_only=True)
    recipes_count = serializers.SerializerMethodField(read_only=True)

    class Meta(UserSerializer.Meta):
        fields = UserSerializer.Meta.fields + ('recipes', 'recipes_count',)
        read_only_fields = ('email', 'username', 'last_name', 'first_name',)

    def validate(self, data):
        author = self.instance
        user = self.context.get('request').user
        if Follow.objects.filter(user=user, author=author).exists():
            raise exceptions.ValidationError(
                detail='Вы уже подписаны на этого пользователя!',
                code=status.HTTP_400_BAD_REQUEST
            )
        if user == author:
            raise exceptions.ValidationError(
                detail='Вы не можете подписаться на самого себя!',
                code=status.HTTP_400_BAD_REQUEST
            )
        return data

    def get_recipes_count(self, obj):
        return obj.recipes.count()

    def get_recipes(self, obj):
        request = self.context.get('request')
        limit = request.GET.get('recipes_limit')
        recipes = obj.recipes.all()
        if limit:
            recipes = recipes[:int(limit)]
        serializer = ShortRecipeSerializer(recipes, many=True, read_only=True)
        return serializer.data


class ShortRecipeSerializer(serializers.ModelSerializer):

    class Meta:
        model = Recipe
        fields = ("id", "name", "image", "cooking_time")


class TagSerializer(serializers.ModelSerializer):

    class Meta:
        model = Tag
        fields = (
            'id',
            'name',
            'slug',
        )


class IngredientSerializer(serializers.ModelSerializer):

    class Meta:
        model = Ingredient
        fields = ("id", "name", "measurement_unit")


class IngredientInRecipeSerializer(serializers.ModelSerializer):

    id = serializers.PrimaryKeyRelatedField(
        read_only=True,
        source='ingredient'
    )

    name = serializers.SlugRelatedField(
        source='ingredient',
        read_only=True,
        slug_field='name'
    )

    measurement_unit = serializers.SlugRelatedField(
        source='ingredient',
        read_only=True,
        slug_field='measurement_unit'
    )

    class Meta:
        model = IngredientInRecipe
        fields = '__all__'


class IngredientInRecipeWriteSerializer(serializers.ModelSerializer):

    id = serializers.PrimaryKeyRelatedField(queryset=Ingredient.objects.all())

    class Meta:
        model = IngredientInRecipe
        fields = ('id', 'amount')


class RecipeReadSerializer(serializers.ModelSerializer):

    tags = TagSerializer(many=True, read_only=True)
    author = UserSerializer(read_only=True)
    ingredients = IngredientInRecipeSerializer(many=True,
                                               required=True,
                                               source='ingredient_list')
    image = Base64ImageField()
    is_favorited = serializers.SerializerMethodField()
    is_in_shopping_cart = serializers.SerializerMethodField()

    class Meta:
        model = Recipe
        fields = (
            'id', 'tags', 'author', 'ingredients', 'is_favorited',
            'is_in_shopping_cart', 'name', 'image', 'text', 'cooking_time',
        )

    def get_ingredients(self, recipe):
        return recipe.ingredients.values(
            'id',
            'name',
            'measurement_unit',
            amount=models.F('recipes__ingredient_list')
        )

    def get_is_favorited(self, obj):
        return obj.is_favored_by(self.context['request'].user)

    def get_is_in_shopping_cart(self, obj):
        user = self.context['request'].user
        return (
            user.is_authenticated and user.shopping_list.filter(recipe=obj
                                                                ).exists()
        )


class FavoriteSerializer(serializers.ModelSerializer):

    class Meta:
        model = Favourites
        fields = ("user", "recipe")
        validators = [
            UniqueTogetherValidator(
                queryset=Favourites.objects.all(), fields=("user", "recipe")
            )
        ]

    def to_representation(self, instance):
        request = self.context.get('request')
        return ShortRecipeSerializer(
            instance.recipe,
            context={'request': request}
        ).data


class RecipeWriteSerializer(serializers.ModelSerializer):
    """Сериализатор для создания и обновления рецептов."""

    tags = relations.PrimaryKeyRelatedField(queryset=Tag.objects.all(),
                                            many=True)
    author = UserSerializer(read_only=True)
    ingredients = serializers.ListField(child=serializers.DictField(),
                                        write_only=True)
    image = Base64ImageField(max_length=None, use_url=True)

    class Meta:
        model = Recipe
        fields = (
            "id",
            "image",
            "tags",
            "author",
            "ingredients",
            "name",
            "text",
            "cooking_time",
        )
        read_only_fields = ("author",)

    @transaction.atomic
    def add_ingredients(self, ingredients, recipe):
        """Добавляет ингредиенты к рецепту."""
        ingredient_objects = [
            IngredientInRecipe(
                recipe=recipe,
                ingredient_id=ingredient["id"],
                amount=ingredient["amount"],
            )
            for ingredient in ingredients
        ]
        IngredientInRecipe.objects.bulk_create(ingredient_objects)

    def validate_ingredients(self, ingredients):
        """Валидация ингредиентов."""
        if not ingredients:
            raise serializers.ValidationError(
                "Добавьте хотя бы один ингредиент.")
        seen = set()
        for ingredient in ingredients:
            if ingredient["id"] in seen:
                raise serializers.ValidationError(
                    "Ингредиенты должны быть уникальными.")
            if int(ingredient["amount"]) <= 0:
                raise serializers.ValidationError(INGREDIENT_MIN_AMOUNT_ERROR)
            seen.add(ingredient["id"])
        return ingredients

    def validate_tags(self, tags):
        """Валидация тегов."""
        if not tags:
            raise serializers.ValidationError("Добавьте хотя бы один тег.")
        if len(tags) != len(set(tags)):
            raise serializers.ValidationError("Теги должны быть уникальными.")
        return tags

    def validate_cooking_time(self, cooking_time):
        """Валидация времени приготовления."""
        if int(cooking_time) <= 0:
            raise serializers.ValidationError(
                "Время приготовления не может быть меньше одной минуты!"
            )
        return cooking_time

    def create(self, validated_data):
        """Создает новый рецепт."""
        request = self.context.get("request")
        ingredients = validated_data.pop("ingredients")
        tags = validated_data.pop("tags")
        recipe = Recipe.objects.create(author=request.user, **validated_data)
        recipe.tags.set(tags)
        self.add_ingredients(ingredients, recipe)
        return recipe

    def update(self, instance, validated_data):
        """Обновляет существующий рецепт."""
        request = self.context.get("request")
        if instance.author != request.user:
            raise PermissionDenied("Вы не можете редактировать этот рецепт.")
        ingredients = validated_data.pop("ingredients", None)
        tags = validated_data.pop("tags", None)
        instance = super().update(instance, validated_data)
        if tags:
            instance.tags.set(tags)
        if ingredients:
            instance.ingredients.clear()
            self.add_ingredients(ingredients, instance)
        return instance

    def to_representation(self, instance):
        """Возвращает данные в виде сериализованного ответа."""
        request = self.context.get("request")
        context = {"request": request}
        return RecipeReadSerializer(instance, context=context).data
