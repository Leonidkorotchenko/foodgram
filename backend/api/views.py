from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Sum, Exists, OuterRef, Prefetch
from django.shortcuts import get_object_or_404, HttpResponse
from djoser.views import UserViewSet
from django.http import JsonResponse
from rest_framework import (viewsets,
                            permissions,
                            status,
                            exceptions,
                            serializers)
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import SAFE_METHODS, IsAuthenticated
from rest_framework.viewsets import ReadOnlyModelViewSet

from users.models import User, Follow
from .filters import RecipeFilter, IngredientFilter
from .models import (
    Tag,
    Recipe,
    Ingredient,
    ShoppingCart,
    IngredientInRecipe,
    Favorites
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
    FollowCreateSerializer,
    ShoppingCartSerializer,
)
from .permissions import AuthorOrReadOnly


class UserViewSet(UserViewSet):
    permission_classes = (IsAuthenticated,)
    serializer_class = UserSerializer
    pagination_class = NumberPagination

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user

        if user.is_authenticated:
            queryset = queryset.annotate(
                is_subscribed=Exists(
                    Follow.objects.filter(
                        user=user,
                        author=OuterRef('pk')
                    )
                )
            )
        else:
            queryset = queryset.annotate(is_subscribed=models
                                         .Value(False,
                                                output_field=models
                                                .BooleanField()))
        return queryset

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
        instance = self.request.user
        if request.method == "PUT":
            serializer = AvatarSerializer(instance, data=request.data)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
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

        if request.method == "POST":
            serializer = FollowCreateSerializer(
                data={'user': user.id, 'author': author.id},
                context={'request': request}
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()

            author_serializer = FollowSerializer(
                author,
                context={"request": request}
            )
            return Response(
                author_serializer.data,
                status=status.HTTP_201_CREATED
            )

        subscription = Follow.objects.filter(user=user, author=author)
        if not subscription.exists():
            return Response(
                {"errors": "Подписка не найдена"},
                status=status.HTTP_400_BAD_REQUEST
            )
        subscription.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(
        methods=["GET"],
        detail=False,
        permission_classes=[IsAuthenticated],
    )
    def me(self, request):
        user = request.user
        user = User.objects.filter(pk=user.pk).annotate(
            is_subscribed=Exists(
                Follow.objects.filter(
                    user=request.user,
                    author=OuterRef('pk')))).first()
        serializer = self.get_serializer(user)
        return Response(serializer.data)

    @action(
        methods=["GET"],
        detail=False,
        permission_classes=[IsAuthenticated],
    )
    def subscriptions(self, request):
        queryset = User.objects.filter(
            following__user=request.user
        ).prefetch_related(
            Prefetch(
                'recipes',
                queryset=Recipe.objects.order_by('-pub_date')
            )
        )

        limit = request.query_params.get('limit')
        if limit and limit.isdigit():
            limit = int(limit)
            for user in queryset:
                user.recipes.set(user.recipes.all()[:limit])

        page = self.paginate_queryset(queryset)
        serializer = FollowSerializer(
            page,
            many=True,
            context={'request': request}
        )
        return self.get_paginated_response(serializer.data)


class TagViewSet(ReadOnlyModelViewSet):
    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    permission_classes = (permissions.AllowAny,)
    pagination_class = None


class IngredientViewSet(ReadOnlyModelViewSet):
    queryset = Ingredient.objects.all()
    serializer_class = IngredientSerializer
    permission_classes = (permissions.AllowAny,)
    filterset_class = IngredientFilter
    pagination_class = None

    def get_queryset(self):
        queryset = super().get_queryset()
        return self.filter_queryset(queryset)


class RecipeViewSet(viewsets.ModelViewSet):
    queryset = Recipe.objects.all()
    permission_classes = (AuthorOrReadOnly,)
    serializer_class = RecipeReadSerializer
    filterset_class = RecipeFilter
    pagination_class = NumberPagination
    http_method_names = ['get',
                         'post',
                         'put',
                         'patch',
                         'delete',
                         'head',
                         'options']

    def get_queryset(self):
        queryset = super().get_queryset()
        return self.filter_queryset(queryset)

    def get_serializer_class(self):
        if self.request.method in ['POST', 'PUT', 'PATCH']:
            return RecipeWriteSerializer
        if self.request.method in SAFE_METHODS:
            return RecipeReadSerializer

    def create(self, request, *args, **kwargs):
        try:
            return super().create(request, *args, **kwargs)
        except serializers.ValidationError as e:
            return Response(
                e.detail,
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception:
            return Response(
                {"detail": "Ошибка при создании рецепта"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @staticmethod
    def recipe_action(request, pk, model, serializer_class, error_message):
        recipe = get_object_or_404(Recipe, id=pk)
        user = request.user

        if request.method == "POST":
            serializer = serializer_class(
                data={"user": user.id, "recipe": recipe.id},
                context={"request": request}
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(
                ShortRecipeSerializer(recipe).data,
                status=status.HTTP_201_CREATED
            )

        relation = model.objects.filter(user=user, recipe=recipe)
        if not relation.exists():
            raise exceptions.ValidationError({"errors": error_message})
        relation.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(
        methods=["POST", "DELETE"],
        detail=True,
        permission_classes=[IsAuthenticated],
    )
    def favorite(self, request, pk):
        return self.recipe_action(
            request=request,
            pk=pk,
            model=Favorites,
            serializer_class=FavoriteSerializer,
            error_message="Этого рецепта нет в избранном."
        )

    @action(
        methods=['POST', 'DELETE'],
        detail=True,
        permission_classes=[IsAuthenticated]
    )
    def shopping_cart(self, request, pk):
        return self.recipe_action(
            request=request,
            pk=pk,
            model=ShoppingCart,
            serializer_class=ShoppingCartSerializer,
            error_message="Рецепта нет в корзине."
        )

    @action(detail=False,
            methods=['GET'],
            permission_classes=[IsAuthenticated])
    def download_shopping_cart(self, request):
        user = request.user

        ingredients = (
            IngredientInRecipe.objects
            .filter(recipe__in_shopping_carts__user=user)
            .values('ingredient__name', 'ingredient__measurement_unit')
            .annotate(total=Sum('amount'))
            .order_by('ingredient__name')
        )

        text = '\n'.join([(
            f"{item['ingredient__name']} "
            f"({item['ingredient__measurement_unit']}) - {item['total']}")
            for item in ingredients
        ])

        response = HttpResponse(text, content_type='text/plain')
        attachment = ('attachment; filename="shopping_list.txt"')
        response['Content-Disposition'] = attachment
        return response

    @action(
        detail=True,
        methods=['GET'],
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
