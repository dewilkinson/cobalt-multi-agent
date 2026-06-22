import os

user_dir = "C:/Users/rende"
try:
    print(f"Contents of {user_dir}:")
    for name in os.listdir(user_dir):
        path = os.path.join(user_dir, name)
        is_dir = os.path.isdir(path)
        print(f"  {name} {'(Dir)' if is_dir else '(File)'}")
except Exception as e:
    print(f"Error: {e}")
