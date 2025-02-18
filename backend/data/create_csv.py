import csv

data = [
    ('name', 'slug'),
    ('завтрак', 'breakfast'),
    ('обед', 'lunch'),
    ('ужин', 'dinner'),
    ('коктейль', 'cocktail'),
    ('антре', 'appetizers'),
    ('выпечка', 'baking'),
    ('пища богов', 'the Food of the Gods'),
    ('чайнатаун', 'chinesefood'),
    ('каннам', 'koreanfood'),
    ('как у бабули', 'comfort food')
]

with open("tags.csv", "w", newline="", encoding="utf-8") as file:
    writer = csv.writer(file)
    writer.writerows(data)
