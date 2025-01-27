from rest_framework import serializers
from .models import User


class UserSerializer(serializers.ModelSerializer):

    class Meta:
        model = User
        fields = (
            'username', 'email', 'first_name', 'last_name', 'bio', 'role'
        )


class TagSerializer(serializers.ModelSerializer):
    pass


class IngredientSerializer(serializers.ModelSerializer):
    pass


class RecipeReadSerializer(serializers.ModelSerializer):
    pass
