import csv
import json

csv_filename = "tags.csv"
json_filename = "tags.json"

with open(csv_filename, "r", encoding="utf-8") as csv_file:
    reader = csv.DictReader(csv_file)
    data = list(reader)

with open(json_filename, "w", encoding="utf-8") as json_file:
    json.dump(data, json_file, ensure_ascii=False, indent=4)
