from datetime import datetime as dt


def render_shopping_list(ingredients, recipes):
    # Проверка на корректность данных `ingredients`
    for ingredient in ingredients:
        if not all(key in ingredient for key in ['ingredient__name',
                                                 'total_amount',
                                                 'ingredient__measurement_unit'
                                                 ]
                   ):
            raise ValueError("Некорректный формат данных в ingredients")

    # Проверка на корректность данных `recipes`
    if not all(hasattr(recipe, "name") for recipe in recipes):
        raise ValueError("Некорректный формат данных в recipes")

    # Форматирование времени
    current_date = dt.now().strftime('%d-%m-%Y')

    # Обработка пустого списка ингредиентов
    ingredients_section = (
        '\n'.join([
            f'{index}. {ingredient["ingredient__name"].capitalize()}'
            f' — {ingredient["total_amount"]}'
            f' {ingredient["ingredient__measurement_unit"]}'
            for index, ingredient in enumerate(ingredients, 1)
        ]) if ingredients else "Нет ингредиентов"
    )

    # Обработка пустого списка рецептов
    recipes_section = (
        '\n'.join([f'{index}. {recipe.name}' for index, recipe in enumerate(
            recipes, 1
            )
                   ]) if recipes else "Нет рецептов"
    )

    # Финальное объединение текста
    return '\n'.join([
        f"Список покупок составлен: {current_date}",
        "Список продуктов:",
        ingredients_section,
        "",
        "Рецепты, для которых составлен список покупок:",
        recipes_section
    ])
