import base64

from django.db import models, transaction
from django.core.files.base import ContentFile
from rest_framework import serializers, exceptions, status, fields, relations
from rest_framework.exceptions import PermissionDenied
from rest_framework.validators import UniqueTogetherValidator
from users.models import User, Follow
from .models import (
    Recipe,
    Tag,
    Ingredient,
    IngredientInRecipe,
    RecipeIngredient,
    Favourites
    )


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = (
            'username', 'email', 'first_name', 'last_name', 'bio', 'role'
        )


class Base64ImageField(serializers.ImageField):
    def to_internal_value(self, data):
        if isinstance(data, str) and data.startswith('data:image'):
            format, imgstr = data.split(';base64,')
            ext = format.split('/')[-1]

            data = ContentFile(base64.b64decode(imgstr), name='temp.' + ext)

        return super().to_internal_value(data)


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
    is_favorited = fields.SerializerMethodField(read_only=True)
    is_in_shopping_cart = fields.SerializerMethodField(read_only=True)

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
        request = self.context.get('request')
        return (request and request.user.is_authenticated
                and request.user.favourites.filter(recipe=obj).exists())

    def get_is_in_shopping_cart(self, obj):
        request = self.context.get('request')
        return (request and request.user.is_authenticated
                and request.user.shopping_list.filter(recipe=obj).exists())


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

    tags = relations.PrimaryKeyRelatedField(queryset=Tag.objects.all(),
                                            many=True)
    author = UserSerializer(read_only=True)
    ingredients = IngredientInRecipeWriteSerializer(many=True)
    image = Base64ImageField(max_length=None, use_url=True)

    class Meta:
        model = Recipe
        fields = ('id', 'image', 'tags', 'author', 'ingredients',
                  'name', 'text', 'cooking_time')
        read_only_fields = ('author',)

    @transaction.atomic
    def create_bulk_ingredients(self, ingredients, recipe):
        for ingredient in ingredients:
            IngredientInRecipe.objects.get_or_create(
                recipe=recipe,
                ingredient=ingredient['id'],
                amount=ingredient['amount']
            )

    def validate(self, data):
        ingredients = data.get("ingredients")
        tags = data.get("tags")
        if not ingredients:
            raise serializers.ValidationError(
                "Необходимо добавить хотя бы один ингредиент."
            )
        if not tags:
            raise serializers.ValidationError(
                "Необходимо добавить хотя бы один тег."
            )
        if len(tags) != len(set(tags)):
            raise serializers.ValidationError("Теги должны быть уникальными.")
        if len(set(val["id"] for val in ingredients)) != len(ingredients):
            raise serializers.ValidationError(
                "Ингредиенты должны быть уникальными."
            )
        return data

    def add_ingredients(self, ingredients, recipe):
        RecipeIngredient.objects.bulk_create(
            [
                RecipeIngredient(
                    recipe=recipe,
                    ingredient=ingredient["id"],
                    amount=ingredient["amount"],
                )
                for ingredient in ingredients
            ]
        )

    def create(self, validated_data):
        request = self.context.get("request")
        ingredients = validated_data.pop("ingredients")
        tags = validated_data.pop("tags")
        recipe = Recipe.objects.create(author=request.user, **validated_data)
        recipe.tags.set(tags)
        self.add_ingredients(ingredients, recipe)
        return recipe

    def update(self, instance, validated_data):
        if instance.author != self.context["request"].user:
            raise PermissionDenied(
                "У вас нет прав на редактирование этого рецепта."
            )
        image = validated_data.get("image")
        if not image:
            raise serializers.ValidationError(
                'Поле "image" не может быть пустым.', code="invalid_image"
            )
        tags = validated_data.pop("tags")
        ingredients = validated_data.pop("ingredients")
        recipe = super().update(instance, validated_data)
        if tags:
            recipe.tags.clear()
            recipe.tags.set(tags)
        if ingredients:
            recipe.ingredients.clear()
            self.add_ingredients(ingredients, recipe)
        return recipe

    def validate_ingredients(self, value):
        ingredients = self.initial_data.get('ingredients')
        if len(ingredients) <= 0:
            raise exceptions.ValidationError(
                {'ingredients': 'Количество ингредиентов не может быть меньше {min_value}!'}
            )
        ingredients_list = []
        for item in ingredients:
            if item['id'] in ingredients_list:
                raise exceptions.ValidationError(
                    {'ingredients': 'Ингредиенты не могут повторяться!'}
                )
            ingredients_list.append(item['id'])
            if int(item['amount']) <= 0:
                raise exceptions.ValidationError(
                    {'amount': 'Количество ингредиентов не может быть меньше {min_value}!'}
                )
        return value

    def validate_cooking_time(self, data):
        cooking_time = self.initial_data.get('cooking_time')
        if int(cooking_time) <= 0:
            raise serializers.ValidationError(
                'Время приготовления не может быть меньше одной минуты!'
            )
        return data

    def validate_tags(self, value):
        tags = value
        if not tags:
            raise exceptions.ValidationError(
                {'tags': 'Рецепт не может быть без тегов!'}
            )
        tags_list = []
        for tag in tags:
            if tag in tags_list:
                raise exceptions.ValidationError(
                    {'tags': 'Теги должны быть уникальными!'}
                )
            tags_list.append(tag)
        return value

    def to_representation(self, instance):
        request = self.context.get('request')
        context = {'request': request}
        return RecipeReadSerializer(instance,
                                    context=context).data
