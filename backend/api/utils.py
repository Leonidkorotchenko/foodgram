from datetime import datetime as dt


def render_shopping_list(ingredients, recipes):
    current_date = dt.now().strftime('%d-%m-%Y')
    
    ingredients_section = '\n'.join([
        f'{index}. {ing["ingredient__name"]} '
        f'({ing["ingredient__measurement_unit"]}) - {ing["total"]}'
        for index, ing in enumerate(ingredients, 1)
    ]) if ingredients else "Нет ингредиентов"
    
    return '\n'.join([
        f"Список покупок составлен: {current_date}",
        "Ингредиенты:",
        ingredients_section,
        "\nРецепты:",
        '\n'.join([f'- {recipe.name}' for recipe in recipes]) if recipes else "Нет рецептов"
    ])