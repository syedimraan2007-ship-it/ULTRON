from memory_manager import (
    initialize_database,
    save_memory,
    search_memories,
    get_recent_memories,
)


initialize_database()

print(save_memory(
    "ULTRON memory system initialized."
))

print(save_memory(
    "User is building a local AI assistant called ULTRON."
))

print("\nRECENT MEMORIES")
print("================")

for memory in get_recent_memories():
    print(memory)


print("\nSEARCH")
print("======")

results = search_memories("ULTRON")

for result in results:
    print(result)