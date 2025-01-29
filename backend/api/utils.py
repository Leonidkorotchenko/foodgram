from datetime import datetime as dt


def render_shopping_list(ingredients, recipes):

    return '\n'.join([
        f"Список покупок составлен: {dt.now().strftime('%d-%m-%Y')}",
        "Список продуктов:"
    ] + [
        f'{index}.'
        f' {ingredient["ingredient__name"].capitalize()}'
        f'— {ingredient["total_amount"]}'
        f' {ingredient["ingredient__measurement_unit"]}'
        for index, ingredient in enumerate(ingredients, 1)
    ] + [
        'Рецепты, для которых составлен список покупок:'
    ] + [
        f'{index}. {recipe.name}' for index, recipe in enumerate(recipes, 1)
    ])
