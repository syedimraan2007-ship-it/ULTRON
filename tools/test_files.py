from file_tools import (
    list_files,
    search_files,
    get_file_info,
    read_text_file,
)


print("=" * 60)
print("ULTRON FILE TOOL TEST")
print("=" * 60)


print("\n1. LIST FILES")
print("-------------")

files = list_files("D:\\ultron")

for item in files[:20]:
    print(item)


print("\n2. SEARCH FILES")
print("---------------")

matches = search_files("ultron", "D:\\ultron")

for item in matches:
    print(item)


print("\n3. FILE INFO")
print("------------")

info = get_file_info(
    "D:\\ultron\\core\\ultron.py"
)

print(info)


print("\n4. READ FILE")
print("------------")

content = read_text_file(
    "D:\\ultron\\core\\ultron.py"
)

print(content[:1000])