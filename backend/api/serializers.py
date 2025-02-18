import base64

from django.db import models, transaction
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.shortcuts import get_object_or_404
from django.core.validators import MaxValueValidator, MinValueValidator
from rest_framework import serializers, exceptions, status, relations
from rest_framework.exceptions import PermissionDenied
from rest_framework.validators import UniqueTogetherValidator
from users.models import User, Follow
from .models import (
    Recipe,
    Tag,
    Ingredient,
    IngredientInRecipe,
    Favorites
)
from foodgram_backend.constants import INGREDIENT_MIN_AMOUNT_ERROR


class Base64ImageField(serializers.ImageField):
    """Кастомное поле для обработки изображений в формате base64."""

    def to_internal_value(self, data):
        try:
            format, imgstr = data.split(";base64,")
            ext = format.split("/")[-1]
            data = ContentFile(base64.b64decode(imgstr),
                               name=f"temp.{ext}")
        except Exception as e:
            raise serializers.ValidationError(
                f"Ошибка обработки изображения: {str(e)}")
        return super().to_internal_value(data)


class UserSerializer(serializers.ModelSerializer):
    """Сериализатор пользователя."""

    first_name = serializers.CharField(required=True)
    last_name = serializers.CharField(required=True)
    is_subscribed = serializers.SerializerMethodField()
    avatar = serializers.SerializerMethodField()

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

    def get_is_subscribed(self, obj):
        user = self.context.get("request").user
        if user.is_authenticated:
            return Follow.objects.filter(user=user, author=obj).exists()
        return False

    def get_avatar(self, obj):
        if obj.avatar:
            return self.context["request"].build_absolute_uri(obj.avatar.url)
        return None

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
        if user.following.filter(author=author).exists():
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
        recipes = obj.recipes.all()
        recipes_limit = request.query_params.get('recipes_limit')
        if recipes_limit and recipes_limit.isdigit():
            recipes = recipes[:int(recipes_limit)]
        return ShortRecipeSerializer(recipes, many=True).data


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
        source='ingredient.id',
        read_only=True
    )
    name = serializers.CharField(
        source='ingredient.name',
        read_only=True
    )
    measurement_unit = serializers.CharField(
        source='ingredient.measurement_unit',
        read_only=True
    )

    class Meta:
        model = IngredientInRecipe
        fields = ('id', 'name', 'measurement_unit', 'amount')


class IngredientInRecipeWriteSerializer(serializers.ModelSerializer):

    id = serializers.PrimaryKeyRelatedField(queryset=Ingredient.objects.all(),
                                            write_only=True)

    class Meta:
        model = IngredientInRecipe
        fields = ('id', 'amount')


class RecipeReadSerializer(serializers.ModelSerializer):

    tags = TagSerializer(many=True, read_only=True)
    author = UserSerializer(read_only=True)
    ingredients = IngredientInRecipeSerializer(many=True,
                                               required=True,
                                               source="recipe_list")
    image = Base64ImageField()
    is_favorited = serializers.SerializerMethodField()
    is_in_shopping_cart = serializers.SerializerMethodField()
    cooking_time = serializers.IntegerField(
        validators=[
            MinValueValidator(1),
            MaxValueValidator(32000)
        ]
    )

    class Meta:
        model = Recipe
        fields = ('id',
                  'tags',
                  'author',
                  'ingredients',
                  'image',
                  'is_favorited',
                  'is_in_shopping_cart',
                  'cooking_time',
                  'name',
                  'text')
        read_only_fields = ('author',)

    def get_ingredients(self, obj):
        return obj.ingredient_list.values(
            'ingredient__id',
            'ingredient__name',
            'ingredient__measurement_unit',
            'amount'
        )

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['tags'] = TagSerializer(instance.tags.all(), many=True).data
        return data

    def get_is_favorited(self, obj):
        user = self.context.get('request').user
        return user.is_authenticated and obj.in_favorites.filter(user=user).exists()
    
    def get_is_in_shopping_cart(self, obj):
        user = self.context.get('request').user
        return user.is_authenticated and obj.in_shopping_carts.filter(user=user).exists()


class FavoriteSerializer(serializers.ModelSerializer):

    class Meta:
        model = Favorites
        fields = ("user", "recipe")
        validators = [
            UniqueTogetherValidator(
                queryset=Favorites.objects.all(),
                fields=("user", "recipe")
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

    author = UserSerializer(read_only=True)
    ingredients = IngredientInRecipeWriteSerializer(many=True,
                                                    required=True)
    tags = serializers.PrimaryKeyRelatedField(
        queryset=Tag.objects.all(), many=True, required=True
    )
    image = Base64ImageField(
        required=True,
        error_messages={'required': 'Изображение обязательно'}
    )

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
                ingredient_id=ingredient["id"].id,
                amount=ingredient["amount"],
            )
            for ingredient in ingredients
        ]
        IngredientInRecipe.objects.bulk_create(ingredient_objects)

    def validate_ingredients(self, value):
        if len(value) < 1:
            raise serializers.ValidationError(
                "Добавьте хотя бы один ингредиент"
            )
        
        ingredients = []
        for item in value:
            ingredient_id = item['id']
            if ingredient_id in ingredients:
                raise serializers.ValidationError(
                    "Ингредиенты должны быть уникальными"
                )
            ingredients.append(ingredient_id)
            
            if item['amount'] < 1:
                raise serializers.ValidationError(
                    "Количество должно быть не менее 1"
                )
        return value
    
    def validate(self, data):
    # Добавить общую валидацию для рецептов
        if 'ingredients' not in data:
            raise serializers.ValidationError(
                {"ingredients": "Требуется хотя бы один ингредиент"}
            )
        
        if 'tags' not in data or len(data['tags']) == 0:
            raise serializers.ValidationError(
                {"tags": "Требуется хотя бы один тег"}
            )
        
        return data

    @transaction.atomic
    def create(self, validated_data):
        try:
            ingredients = validated_data.pop("ingredients")
            tags = validated_data.pop("tags")
            recipe = Recipe.objects.create(
                author=self.context["request"].user,
                **validated_data
            )
            recipe.tags.set(tags)
        
            # Создание объектов IngredientInRecipe с проверкой
            ingredient_objects = []
            for ingredient_data in ingredients:
                ingredient = ingredient_data['id']
                amount = ingredient_data['amount']
            
                if amount < 1:
                    raise serializers.ValidationError(
                        {"amount": "Количество должно быть не менее 1"}
                    )
                
                ingredient_objects.append(
                    IngredientInRecipe(
                        recipe=recipe,
                        ingredient=ingredient,
                        amount=amount
                    )
                )
            
            IngredientInRecipe.objects.bulk_create(ingredient_objects)
            return recipe
        
        except Exception as e:
            raise serializers.ValidationError(
                {"detail": str(e)}
            )

    def validate_tags(self, value):
        if not value:
            raise serializers.ValidationError("Добавьте хотя бы один тег.")
        tags = set()
        for tag in value:
            if tag in tags:
                raise serializers.ValidationError(
                    "Теги должны быть уникальными."
                    )
            tags.add(tag)
        return value

    def validate_cooking_time(self, cooking_time):
        """Валидация времени приготовления."""
        if int(cooking_time) <= 0:
            raise serializers.ValidationError(
                "Время приготовления не может быть меньше одной минуты!"
            )
        return cooking_time

    def update(self, instance, validated_data):
        """Обновляет существующий рецепт."""
        request = self.context.get("request")
        if instance.author != request.user:
            raise PermissionDenied(
                {"detail": "У вас нет прав редактировать этот рецепт"},
                code=status.HTTP_403_FORBIDDEN
            )
        instance.name = validated_data.get('name', instance.name)
        instance.text = validated_data.get('text', instance.text)
        instance.cooking_time = validated_data.get(
            'cooking_time', 
            instance.cooking_time
        )

        if 'image' in validated_data:
            instance.image = validated_data['image']

        if 'tags' in validated_data:
            instance.tags.set(validated_data['tags'])

        if 'ingredients' in validated_data:
            instance.ingredients.clear()
            self.add_ingredients(validated_data['ingredients'], instance)
    
        instance.save()
        return instance
    
    def update_ingredients(self, recipe, ingredients_data):
        """Обновление ингредиентов с сохранением существующих"""
        current_ingredients = {
            str(item.ingredient.id): item 
            for item in recipe.ingredient_list.all()
        }
    
    # Создаем временный список для новых ингредиентов
        new_ingredients = []
    
        for ingredient_data in ingredients_data:
            ingredient_id = str(ingredient_data['id'].id)
            if ingredient_id in current_ingredients:
                # Обновляем существующий ингредиент
                item = current_ingredients[ingredient_id]
                item.amount = ingredient_data['amount']
                item.save()
            else:
                # Добавляем новый ингредиент
                new_ingredients.append(
                    IngredientInRecipe(
                        recipe=recipe,
                        ingredient=ingredient_data['id'],
                        amount=ingredient_data['amount']
                    )
                )
    
        # Удаляем отсутствующие в новом списке
        to_delete_ids = set(current_ingredients.keys()) - {
            str(ing['id'].id) for ing in ingredients_data
        }
        recipe.ingredient_list.filter(ingredient__id__in=to_delete_ids).delete()
    
        # Добавляем новые ингредиенты
        if new_ingredients:
            IngredientInRecipe.objects.bulk_create(new_ingredients)

    def to_representation(self, instance):
        """Возвращает данные в виде сериализованного ответа."""
        request = self.context.get("request")
        context = {"request": request}
        return RecipeReadSerializer(instance, context=context).data
