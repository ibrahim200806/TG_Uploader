try:
    from pyrogram import Client
except Exception as e:
    print(e)
    print("\nInstall pyrogram: pip3 install pyrogram")
    exit(1)

print("Required pyrogram V2 or greater.")
print("Required to add phone number don't use bot token")
API_KEY = int(input("Enter API KEY: "))
API_HASH = input("Enter API HASH: ")
with Client(name="USS", api_id=API_KEY, api_hash=API_HASH, in_memory=True) as app:
    print(app.export_session_string())
