import base64

from django.db import transaction
from django.core.files.base import ContentFile
from django.core.validators import MaxValueValidator, MinValueValidator
from rest_framework import serializers, exceptions, status
from rest_framework.validators import UniqueTogetherValidator
from users.models import User, Follow
from .models import (
    Recipe,
    Tag,
    Ingredient,
    IngredientInRecipe,
    Favorites,
    ShoppingCart
)
from foodgram_backend.constants import MAX_COOKING_TIME, MIN_COOKING_TIME


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


class ShoppingCartSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShoppingCart
        fields = ("user", "recipe")
        validators = [
            UniqueTogetherValidator(
                queryset=ShoppingCart.objects.all(),
                fields=("user", "recipe"),
                message="Рецепт уже в корзине"
            )
        ]

    def validate(self, data):
        if data["user"] == data["recipe"].author:
            raise serializers.ValidationError(
                "Нельзя добавлять свои рецепты в корзину"
            )
        return data


class FollowCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Follow
        fields = ('user', 'author')
        validators = [
            UniqueTogetherValidator(
                queryset=Follow.objects.all(),
                fields=('user', 'author'),
                message="Вы уже подписаны на этого пользователя"
            )
        ]

    def validate(self, data):
        if data['user'] == data['author']:
            raise serializers.ValidationError(
                {"errors": "Нельзя подписаться на себя"}
            )
        return data


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
    cooking_time = serializers.IntegerField(validators=[
        MinValueValidator(MIN_COOKING_TIME),
        MaxValueValidator(MAX_COOKING_TIME)])

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
        read_only_fields = fields

    def get_ingredients(self, obj):
        return obj.ingredient_list.values(
            'ingredient__id',
            'ingredient__name',
            'ingredient__measurement_unit',
            'amount'
        )

    def to_representation(self, instance):
        data = super().to_representation(instance)
        return data

    def get_is_favorited(self, obj):
        user = self.context.get('request').user
        return user.is_authenticated and obj.in_favorites.filter(
            user=user).exists()

    def get_is_in_shopping_cart(self, obj):
        user = self.context.get('request').user
        return user.is_authenticated and obj.in_shopping_carts.filter(
            user=user).exists()


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

        IngredientInRecipe.objects.bulk_create(IngredientInRecipe(
            recipe=recipe,
            ingredient_id=ingredient["id"].id,
            amount=ingredient["amount"],)
            for ingredient in ingredients)

    def validate(self, data):
        if 'ingredients' not in data:
            raise serializers.ValidationError(
                {"ingredients": "Требуется хотя бы один ингредиент"}
            )
        else:
            if len(data['ingredients']) < 1:
                raise serializers.ValidationError(
                    "Добавьте хотя бы один ингредиент"
                )

            ingredient_ids = [item['id'].id for item in data['ingredients']]
            if len(ingredient_ids) != len(set(ingredient_ids)):
                raise serializers.ValidationError(
                    "Ингредиенты должны быть уникальными"
                )

            for item in data['ingredients']:
                if item['amount'] < 1:
                    raise serializers.ValidationError(
                        "Количество должно быть не менее 1"
                    )

        if 'tags' not in data or len(data['tags']) == 0:
            raise serializers.ValidationError(
                {"tags": "Требуется хотя бы один тег"}
            )
        else:
            if not data['tags']:
                raise serializers.ValidationError("Добавьте хотя бы один тег.")
            tags = set()
            for tag in data['tags']:
                if tag in tags:
                    raise serializers.ValidationError(
                        "Теги должны быть уникальными.")
                tags.add(tag)

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
            self.add_ingredients(ingredients, recipe)
        except Exception as e:
            raise serializers.ValidationError(
                {"detail": str(e)}
            )
        return recipe

    def validate_cooking_time(self, cooking_time):
        """Валидация времени приготовления."""
        if int(cooking_time) <= 0:
            raise serializers.ValidationError(
                "Время приготовления не может быть меньше одной минуты!"
            )
        return cooking_time

    @transaction.atomic
    def update(self, instance, validated_data):
        tags_data = validated_data.pop('tags', None)
        ingredients_data = validated_data.pop('ingredients', None)

        instance = super().update(instance, validated_data)

        if tags_data is not None:
            instance.tags.set(tags_data)

        if ingredients_data is not None:
            instance.ingredient_list.all().delete()
            self.add_ingredients(ingredients_data, instance)

        return instance

    def update_ingredients(self, recipe, ingredients_data):
        """Обновление ингредиентов с сохранением существующих"""
        current = {str(item.ingredient.id):
                   item for item in recipe.ingredient_list.all()}

        new_ids = set()
        for ing in ingredients_data:
            ing_id = str(ing['id'].id)
            new_ids.add(ing_id)
            if ing_id in current:
                current[ing_id].amount = ing['amount']
                current[ing_id].save()

        recipe.ingredient_list.exclude(ingredient__id__in=new_ids).delete()

        new_ingredients = [ing for ing in ingredients_data
                           if str(ing['id'].id) not in current]
        if new_ingredients:
            self.add_ingredients(new_ingredients, recipe)

    def to_representation(self, instance):
        """Возвращает данные в виде сериализованного ответа."""
        request = self.context.get("request")
        context = {"request": request}
        return RecipeReadSerializer(instance, context=context).data
