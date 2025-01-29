from django.core.exceptions import ValidationError
from django.db.models import Sum
from django.shortcuts import get_object_or_404
from djoser.views import UserViewSet
from django.http import FileResponse, JsonResponse
from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import SAFE_METHODS, IsAuthenticated
from rest_framework.viewsets import ReadOnlyModelViewSet

from users.models import User, Follow
from .filters import IngredientFilter, RecipeFilter
from .models import (
    Tag,
    Recipe,
    Ingredient,
    ShoppingCart,
    RecipeIngredient,
    )
from .paginations import NumberPagination
from .serializers import (
    AvatarSerializer,
    UserSerializer,
    FollowSerializer,
    TagSerializer,
    IngredientSerializer,
    RecipeReadSerializer,
    RecipeWriteSerializer,
    FavoriteSerializer,
    ShortRecipeSerializer,
)
from .permissions import AuthorOrReadOnly
from .utils import render_shopping_list


class UserViewSet(UserViewSet):
    permission_classes = (permissions.AllowAny,)
    serializer_class = UserSerializer
    pagination_class = NumberPagination

    def get_permissions(self):
        if self.action == "me":
            return (permissions.IsAuthenticated(),)
        if self.action in ("list", "retrieve"):
            return (permissions.AllowAny(),)
        return super().get_permissions()

    @action(
        methods=["PUT", "DELETE"],
        permission_classes=[IsAuthenticated],
        detail=False,
        url_path="me/avatar",
    )
    def avatar(self, request):
        if request.method == "PUT":
            instance = self.get_instance()
            serializer = AvatarSerializer(instance, data=request.data)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(data=serializer.data, status=status.HTTP_200_OK)

        if request.method == "DELETE":
            instance = self.get_instance()
            instance.avatar = None
            instance.save()
            return Response(status=status.HTTP_204_NO_CONTENT)

    @action(
        methods=["POST", "DELETE"],
        permission_classes=[IsAuthenticated],
        detail=True,
    )
    def subscribe(self, request, id):
        user = request.user
        author = get_object_or_404(User, id=id)
        is_subscribed = user.follower.filter(author=author).exists()
        if request.method == "POST":
            if author == user or is_subscribed:
                return Response(status=status.HTTP_400_BAD_REQUEST)
            serializer = FollowSerializer(author, context={"request": request})
            Follow.objects.create(user=user, author=author)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        if not is_subscribed:
            return Response(status=status.HTTP_400_BAD_REQUEST)
        user.follower.filter(author=author).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(
        methods=["GET"],
        detail=False,
        permission_classes=[IsAuthenticated],
    )
    def subscriptions(self, request):
        user = request.user
        queryset = User.objects.filter(following__user=user)
        paginated_queryset = self.paginate_queryset(queryset)
        serializer = FollowSerializer(
            paginated_queryset, many=True, context={"request": request}
        )
        return self.get_paginated_response(serializer.data)


class TagViewSet(ReadOnlyModelViewSet):
    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    permission_classes = (permissions.AllowAny,)


class IngredientViewSet(ReadOnlyModelViewSet):
    queryset = Ingredient.objects.all()
    serializer_class = IngredientSerializer
    permission_classes = (permissions.AllowAny,)
    filterset_class = IngredientFilter


class RecipeViewSet(viewsets.ModelViewSet):
    """Вьюсет рецептов."""
    queryset = Recipe.objects.all()
    permission_classes = (AuthorOrReadOnly,)
    serializer_class = RecipeReadSerializer
    filterset_class = RecipeFilter
    filterset_fields = (
        'is_in_shopping_cart', 'is_favorited', 'tags', 'author'
    )
    pagination_class = NumberPagination

    def get_queryset(self):
        """
        Переопределяем get_queryset, чтобы корректно фильтровать рецепты.
        """
        queryset = super().get_queryset()
        user = self.request.user

        is_in_shopping_cart = self.request.query_params.get(
            'is_in_shopping_cart')
        if is_in_shopping_cart and user.is_authenticated:
            return queryset
        is_favorited = self.request.query_params.get(
            'is_favorited')
        if is_favorited and not user.is_anonymous:
            return queryset

    def get_serializer_class(self):
        if self.request.method in ('POST', 'PUT', 'PATCH'):
            return RecipeWriteSerializer
        if self.request.method in SAFE_METHODS:
            return RecipeReadSerializer

    @action(
        methods=["POST", "DELETE"],
        detail=True,
        permission_classes=[IsAuthenticated],
    )
    def favorite(self, request, pk):
        recipe = get_object_or_404(Recipe, id=pk)
        user = request.user
        if request.method == "POST":
            serializer = FavoriteSerializer(
                data={"user": user.id, "recipe": recipe.id}
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        if request.method == "DELETE":
            is_favorited = user.favourites.filter(recipe=recipe)
            if is_favorited.exists():
                is_favorited.delete()
                return Response(status=status.HTTP_204_NO_CONTENT)
            return Response(
                data={"errors": "Этого рецепта нет в избранном."},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(
        methods=['post', 'delete'],
        detail=True,
        permission_classes=[IsAuthenticated]
    )
    def shopping_cart(self, request, pk):
        if request.method == 'DELETE':
            recipe = get_object_or_404(Recipe, pk=pk)
            try:
                fav_recipe = ShoppingCart.objects.get(
                    recipe=recipe, user=request.user
                )
                fav_recipe.delete()
            except BaseException:
                return Response(status=status.HTTP_400_BAD_REQUEST)
            return Response(status=status.HTTP_204_NO_CONTENT)

        recipe = get_object_or_404(Recipe, pk=pk)
        created = ShoppingCart.objects.get_or_create(
            recipe=recipe, user=request.user)
        if not created[-1]:
            return Response(
                {'errors': 'Рецепт уже добавлен!'},
                status.HTTP_400_BAD_REQUEST
            )
        serializer = ShortRecipeSerializer(
            recipe, context={'request': request}
        )
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'])
    def download_shopping_cart(self, request):
        user = request.user
        shopping_cart = ShoppingCart.objects.filter(user=user)
        if not shopping_cart.exists():
            raise ValidationError({'status': 'Ваш список покупок пуст'})

        ingredients = RecipeIngredient.objects.filter(
            recipe__in=shopping_cart.values_list('recipe', flat=True)).values(
            'ingredient__name',
            'ingredient__measurement_unit').annotate(total_amount=Sum('amount')
                                                     )

        recipes = Recipe.objects.filter(
            id__in=shopping_cart.values_list('recipe', flat=True))
        return FileResponse(render_shopping_list(ingredients, recipes),
                            content_type='text/plain',
                            filename='shopping_list.txt')

    @action(
        detail=True,
        methods=('get', ),
        url_path='get-link',
        url_name='get-link',
        permission_classes=[permissions.IsAuthenticatedOrReadOnly]
    )
    def get_recipe_short_link(self, request, pk=None):
        if not Recipe.objects.filter(id=pk).exists():
            raise ValidationError(
                {'status':
                 f'Рецепт с ID {pk} не найден'})
        short_link = f'{request.build_absolute_uri("/")[:-1]}/r/{str(pk)}/'
        return JsonResponse({'short-link': short_link})
